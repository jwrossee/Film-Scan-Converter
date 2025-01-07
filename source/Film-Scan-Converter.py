import rawpy
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk
import multiprocessing
import threading
import ctypes
import os
import sys
import matplotlib.colors
import psutil
import platform

class GUI:
    def __init__(self, master):
        # Initialize Variables
        self.photos = []
        self.in_progress = set() # keeps track photos that are in processing when first loading
        self.photo_process_values = ['RAW', 'Threshold', 'Contours', 'Histogram', 'Full Preview']
        self.filetypes = ['TIFF', 'PNG', 'JPG'] # Export File Types
        self.destination_folder = ''
        self.allowable_image_filetypes = [
            ('RAW files', '*.DNG *.CR2 *.NEF *.ARW *.RAF *.ERF *.NEF *.GPR *.RAW *.CRW'),
            ('Image files', '*.PNG *.JPG *.JPEG *.BMP *.TIFF *.TIF')
            ]
        self.header_style = ('Segoe UI', 10, 'normal') # Defines font for section headers
        self.wb_picker = False
        self.base_picker = False
        self.unsaved = False # Indicates that settings have changed need to be saved

        self.max_processors_override = 0 # 0 means disabled
        self.preload = 4 # Buffer size to preload photos
        self.advanced_attrs = ('max_processors_override','preload') # attributes that will be picked up for modification in advanced settings

        self.default_settings = dict(
            film_type = 0,
            dark_threshold = 25,
            light_threshold = 100,
            border_crop = 1,
            flip = False,
            white_point = 0,
            black_point = 0,
            gamma = 0,
            shadows = 0,
            highlights = 0,
            temp = 0,
            tint = 0,
            sat = 100,
            base_detect = 0,
            base_rgb = (255, 255, 255),
            remove_dust = False
        )

        self.global_settings = self.default_settings.copy()

        # Building the GUI
        master.title('Film Scan Converter')
        master.state('zoomed')
        master.geometry('800x500')
        validation = master.register(self.validate)

        menubar = tk.Menu(master, relief=tk.FLAT)
        self.filemenu = tk.Menu(menubar, tearoff=0)
        self.filemenu.add_cascade(label='Import...', command=self.import_photos)
        self.filemenu.add_cascade(label='Save Settings', command=self.save_settings)
        self.filemenu.add_separator()
        self.filemenu.add_command(label='Exit', command=self.on_closing)
        menubar.add_cascade(label='File', menu=self.filemenu)
        self.editmenu = tk.Menu(menubar, tearoff=0)
        self.editmenu.add_cascade(label='Reset to Default Settings', command=self.reset_settings)
        self.editmenu.add_separator()
        self.editmenu.add_cascade(label='Advanced Settings...', command=self.advanced_dialog)
        menubar.add_cascade(label='Edit', menu=self.editmenu)
        master.config(menu=menubar)

        mainFrame = ttk.Frame(master, padding=10)
        mainFrame.pack(side=tk.TOP, anchor=tk.NW, fill='both', expand=True)
        mainFrame.grid_rowconfigure(0, weight=1)
        mainFrame.grid_columnconfigure(1, weight=1)

        self.controlsFrame = ttk.Frame(mainFrame)
        self.controlsFrame.grid(row=0, column=0, sticky='NS', rowspan=10)
        self.controlsFrame.grid_rowconfigure(0, weight=1)
        self.controlsFrame.grid_columnconfigure(0, weight=1)
        dynamic_scroll_frame = ScrollFrame(self.controlsFrame)

        # Importing RAW scans
        import_title = ttk.Label(text='Select Photo', font=self.header_style, padding=2)
        importFrame = ttk.LabelFrame(dynamic_scroll_frame.frame, borderwidth=2, labelwidget=import_title, padding=5)
        importFrame.grid(row=0, column=0, sticky='EW')
        importSubFrame1 = ttk.Frame(importFrame)
        importSubFrame1.pack(fill='x')
        ttk.Label(importSubFrame1, text='RAW File:').pack(side=tk.LEFT)
        self.photoCombo = ttk.Combobox(importSubFrame1, state='readonly')
        self.photoCombo.bind('<<ComboboxSelected>>', self.load_IMG)
        self.photoCombo.pack(side=tk.LEFT, padx=2)
        self.import_button = ttk.Button(importSubFrame1, text='Import...', command=self.import_photos, width=8)
        self.import_button.pack(side=tk.LEFT, padx=2)
        importSubFrame2 = ttk.Frame(importFrame)
        importSubFrame2.pack(fill='x')
        self.prevButton = ttk.Button(importSubFrame2, text='< Previous Photo', width=20, command=self.previous)
        self.prevButton.pack(side=tk.LEFT, padx=2, pady=5)
        self.nextButton = ttk.Button(importSubFrame2, text='Next Photo >', width=20, command=self.next)
        self.nextButton.pack(side=tk.LEFT, padx=2, pady=5)

        # Processing Frame
        processing_title = ttk.Label(text='Processing Settings', font=self.header_style, padding=2)
        processingFrame = ttk.LabelFrame(dynamic_scroll_frame.frame, borderwidth=2, labelwidget=processing_title, padding=5)
        processingFrame.grid(row=1, column=0, sticky='EW')
        # Reject Checkbutton to exclude from export
        rejectFrame = ttk.Frame(processingFrame)
        rejectFrame.grid(row=0, column=0, sticky='EW')
        ttk.Label(rejectFrame, text='Reject Photo:').pack(side=tk.LEFT)
        self.reject_check = tk.BooleanVar()
        self.reject_check.set(False)
        self.reject_CheckButton = ttk.Checkbutton(rejectFrame, variable=self.reject_check, state='deselected', command=self.set_reject)
        self.reject_CheckButton.pack(side=tk.LEFT)
        # Selection of global settings
        self.globFrame = ttk.Frame(processingFrame)
        self.globFrame.grid(row=1, column=0, sticky='EW')
        ttk.Label(self.globFrame, text='Sync with Global Settings:').pack(side=tk.LEFT)
        self.glob_check = tk.BooleanVar()
        self.glob_check.set(True)
        ttk.Checkbutton(self.globFrame, variable=self.glob_check, state='selected', command=self.set_global).pack(side=tk.LEFT)
        # Selection of film type
        self.filmFrame = ttk.Frame(processingFrame)
        self.filmFrame.grid(row=3, column=0, sticky='EW')
        ttk.Label(self.filmFrame, text='Film Type:').pack(side=tk.LEFT)
        self.filmCombo = ttk.Combobox(self.filmFrame, state='readonly', values=['Black & White Negative', 'Colour Negative', 'Slide (Colour Positive)','Crop Only (RAW)'], width=25)
        self.filmCombo.current(self.global_settings['film_type'])
        self.filmCombo.pack(side=tk.LEFT, padx=2)
        self.filmCombo.bind('<<ComboboxSelected>>', self.set_film_type)
        # Dust removal
        self.dustFrame = ttk.Frame(processingFrame)
        self.dustFrame.grid(row=4, column=0, sticky='EW')
        ttk.Label(self.dustFrame, text='Remove Dust:').pack(side=tk.LEFT)
        self.dust_check = tk.BooleanVar()
        self.dust_check.set(self.global_settings['remove_dust'])
        ttk.Checkbutton(self.dustFrame, variable=self.dust_check, state='deselected', command=self.set_remove_dust).pack(side=tk.LEFT)

        # Automatic Cropping Settings
        controls_title = ttk.Label(text='Automatic Crop & Rotate', font=self.header_style, padding=2)
        self.cropFrame = ttk.LabelFrame(dynamic_scroll_frame.frame, borderwidth=2, labelwidget=controls_title, padding=5)
        self.cropFrame.grid(row=4, column=0, sticky='EW')
        crop_adjustments = ttk.Frame(self.cropFrame)
        crop_adjustments.pack(fill='x')
        crop_adjustments.grid_rowconfigure(1, weight=1)
        crop_adjustments.grid_columnconfigure(3, weight=1)
        ttk.Label(crop_adjustments, text='Dark Threshold:').grid(row=0, column=0, sticky=tk.E)
        self.dark_threshold = tk.IntVar()
        self.dark_threshold.set(self.global_settings['dark_threshold'])
        self.dark_threshold_scale = ttk.Scale(crop_adjustments, from_=0, to=100, orient=tk.HORIZONTAL, command=lambda x:self.dark_threshold.set(round(float(x))), length=100, value=self.dark_threshold.get())
        self.dark_threshold_scale.grid(row=0, column=1, padx=2)
        self.dark_threshold_scale.bind('<ButtonRelease-1>', self.set_dark_threshold)
        self.dark_threshold_spin = ttk.Spinbox(crop_adjustments, from_=0, to=100, increment=1, textvariable=self.dark_threshold, command=self.set_dark_threshold, width=5, validate='key', validatecommand=(validation, '%P', '%W'))
        self.dark_threshold_spin.grid(row=0, column=2)
        self.dark_threshold_spin.bind('<Return>', self.set_dark_threshold)
        self.dark_threshold_spin.bind('<FocusOut>', self.set_dark_threshold)
        ttk.Label(crop_adjustments, text='Light Threshold:').grid(row=1, column=0, sticky=tk.E)
        self.light_threshold = tk.IntVar()
        self.light_threshold.set(self.global_settings['light_threshold'])
        self.light_threshold_scale = ttk.Scale(crop_adjustments, from_=0, to=100, orient=tk.HORIZONTAL, command=lambda x:self.light_threshold.set(round(float(x))), length=100, value=self.light_threshold.get())
        self.light_threshold_scale.grid(row=1, column=1, padx=2)
        self.light_threshold_scale.bind('<ButtonRelease-1>', self.set_light_threshold)
        self.light_threshold_spin = ttk.Spinbox(crop_adjustments, from_=0, to=100, increment=1, textvariable=self.light_threshold, command=self.set_light_threshold, width=5, validate='key', validatecommand=(validation, '%P', '%W'))
        self.light_threshold_spin.grid(row=1, column=2)
        self.light_threshold_spin.bind('<Return>', self.set_light_threshold)
        self.light_threshold_spin.bind('<FocusOut>', self.set_light_threshold)
        ttk.Label(crop_adjustments, text='Border Crop (%):').grid(row=2, column=0, sticky=tk.E)
        self.border_crop = tk.IntVar()
        self.border_crop.set(self.global_settings['border_crop'])
        self.bc_scale = ttk.Scale(crop_adjustments, from_=0, to=20, orient=tk.HORIZONTAL, command=lambda x:self.border_crop.set(round(float(x))), length=100, value=self.border_crop.get())
        self.bc_scale.grid(row=2, column=1, padx=2)
        self.bc_scale.bind('<ButtonRelease-1>', self.set_border_crop)
        self.bc_spin = ttk.Spinbox(crop_adjustments, from_=0, to=20, textvariable=self.border_crop, width=5, command=self.set_border_crop, validate='key', validatecommand=(validation, '%P', '%W'))
        self.bc_spin.grid(row=2, column=2)
        self.bc_spin.bind('<Return>', self.set_border_crop)
        self.bc_spin.bind('<FocusOut>', self.set_border_crop)
        ttk.Label(crop_adjustments, text='Flip Horizontally:').grid(column=0, row=3, sticky=tk.E)
        self.flip_check = tk.BooleanVar()
        self.flip_check.set(self.global_settings['flip'])
        ttk.Checkbutton(crop_adjustments, variable=self.flip_check, state='selected', command=self.set_flip).grid(column=1, row=3, sticky=tk.W)
        rotButtons = ttk.Frame(self.cropFrame)
        rotButtons.pack(fill='x')
        ttk.Button(rotButtons, text='Rotate Counterclockwise', width=22, command=self.rot_counterclockwise).pack(side=tk.LEFT, padx=2, pady=5)
        ttk.Button(rotButtons, text='Rotate Clockwise', width=22, command=self.rot_clockwise).pack(side=tk.LEFT, padx=2, pady=5)

        # Colour settings
        if getattr(sys, 'frozen', False):
            picker = tk.PhotoImage(file=os.path.join(sys._MEIPASS, 'dropper.png')).subsample(15,15)
        else:
            picker = tk.PhotoImage(file=os.path.join(os.path.dirname(__file__), 'dropper.png')).subsample(15,15)
        colour_title = ttk.Label(text='Colour Adjustment', font=self.header_style, padding=2)
        self.colourFrame = ttk.LabelFrame(dynamic_scroll_frame.frame, borderwidth=2, labelwidget=colour_title, padding=5)
        colour_controls = ttk.Frame(self.colourFrame)
        colour_controls.pack(fill='x', side=tk.LEFT)
        ttk.Label(colour_controls, text='Film Base Colour:').grid(row=0, column=0, sticky=tk.E)
        self.base = ttk.Combobox(colour_controls, values=['Auto Detect','Set Manually'], state='readonly', width=12)
        self.base.grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=2)
        self.base.current(self.global_settings['base_detect'])
        self.base.bind('<<ComboboxSelected>>', self.set_base_detect)
        self.base_clr_lbl = ttk.Label(colour_controls, text='RGB:')
        self.base_rgb = tk.StringVar()
        self.base_rgb.set(str(self.global_settings['base_rgb']))
        self.base_rgb_lbl = ttk.Label(colour_controls, textvariable=self.base_rgb)
        self.rgb_display = tk.Frame(colour_controls, bg=self._from_rgb(self.global_settings['base_rgb']), height=20, width=20, relief=tk.GROOVE, borderwidth=1)
        self.base_pick_button = ttk.Button(colour_controls, image=picker, command=self.set_base)
        self.base_pick_button.image = picker
        self.base_buttons_frame = ttk.Frame(colour_controls)
        ttk.Button(self.base_buttons_frame, text='Set RGB', command=lambda:self.set_base_rgb(0), width=8).pack(side=tk.LEFT, padx=2, pady=2, anchor='center')
        ttk.Button(self.base_buttons_frame, text='Import Blank...', command=lambda:self.set_base_rgb(2), width=13).pack(side=tk.LEFT, padx=2, pady=2, anchor='center')
        ttk.Label(colour_controls, text='White Balance Picker:').grid(row=3, column=0, sticky=tk.E)
        self.wb_picker_button = ttk.Button(colour_controls, image=picker, command=self.pick_wb)
        self.wb_picker_button.grid(row=3, column=1, sticky=tk.W)
        self.wb_picker_button.image = picker
        ttk.Label(colour_controls, text='Temperature:').grid(row=4, column=0, sticky=tk.E, padx=2, pady=2)
        self.temp = tk.IntVar()
        self.temp.set(self.global_settings['temp'])
        self.temp_scale = ttk.Scale(colour_controls, from_=-100, to=100, orient=tk.HORIZONTAL, command=lambda x:self.temp.set(round(float(x)/5)*5), length=100, value=self.temp.get())
        self.temp_scale.grid(row=4, column=1, padx=2)
        self.temp_scale.set(self.global_settings['temp'])
        self.temp_scale.bind('<ButtonRelease-1>', self.set_temp)
        self.temp_spin = ttk.Spinbox(colour_controls, from_=-100, to=100, increment=5, textvariable=self.temp, width=5, command=self.set_temp, validate='key', validatecommand=(validation, '%P', '%W'))
        self.temp_spin.grid(row=4, column=2, sticky=tk.W, columnspan=2)
        self.temp_spin.bind('<Return>', self.set_temp)
        self.temp_spin.bind('<FocusOut>', self.set_temp)
        ttk.Label(colour_controls, text='Tint:').grid(row=5, column=0, sticky=tk.E)
        self.tint = tk.IntVar()
        self.tint.set(self.global_settings['tint'])
        self.tint_scale = ttk.Scale(colour_controls, from_=-100, to=100, orient=tk.HORIZONTAL, command=lambda x:self.tint.set(round(float(x)/5)*5), length=100, value=self.tint.get())
        self.tint_scale.grid(row=5, column=1, padx=2)
        self.tint_scale.set(self.global_settings['tint'])
        self.tint_scale.bind('<ButtonRelease-1>', self.set_tint)
        self.tint_spin = ttk.Spinbox(colour_controls, from_=-100, to=100, increment=5, textvariable=self.tint, width=5, command=self.set_tint, validate='key', validatecommand=(validation, '%P', '%W'))
        self.tint_spin.grid(row=5, column=2, sticky=tk.W, columnspan=2)
        self.tint_spin.bind('<Return>', self.set_tint)
        self.tint_spin.bind('<FocusOut>', self.set_tint)
        ttk.Label(colour_controls, text='Saturation (%):').grid(row=6, column=0, sticky=tk.E)
        self.sat = tk.IntVar()
        self.sat.set(self.global_settings['sat'])
        self.sat_scale = ttk.Scale(colour_controls, from_=0, to=200, orient=tk.HORIZONTAL, command=lambda x:self.sat.set(round(float(x)/10)*10), length=100, value=self.sat.get())
        self.sat_scale.grid(row=6, column=1, padx=2)
        self.sat_scale.set(self.global_settings['sat'])
        self.sat_scale.bind('<ButtonRelease-1>', self.set_sat)
        self.sat_spin = ttk.Spinbox(colour_controls, from_=0, to=200, increment=10, textvariable=self.sat, width=5, command=self.set_sat, validate='key', validatecommand=(validation, '%P', '%W'))
        self.sat_spin.grid(row=6, column=2, sticky=tk.W, columnspan=2)
        self.sat_spin.bind('<Return>', self.set_sat)
        self.sat_spin.bind('<FocusOut>', self.set_sat)
        
        # Brightness Settings
        brightness_title = ttk.Label(text='Brightness Adjustment', font=self.header_style, padding=2)
        self.exposureFrame = ttk.LabelFrame(dynamic_scroll_frame.frame, borderwidth=2, labelwidget=brightness_title, padding=5)
        self.exposureFrame.grid(row=7, column=0, sticky='EW')
        exposureControls = ttk.Frame(self.exposureFrame)
        exposureControls.pack(fill='x', side=tk.LEFT)
        exposureControls.grid_rowconfigure(6, weight=1)
        exposureControls.grid_columnconfigure(3, weight=1)
        ttk.Label(exposureControls, text='White Point:').grid(row=2, column=0, sticky=tk.E)
        self.white_point = tk.IntVar()
        self.white_point.set(self.global_settings['white_point'])
        self.wpp_scale = ttk.Scale(exposureControls, from_=-100, to=100, orient=tk.HORIZONTAL, command=lambda x:self.white_point.set(round(float(x)/5)*5), length=100, value=self.white_point.get())
        self.wpp_scale.grid(row=2, column=1, padx=2)
        self.wpp_scale.set(self.global_settings['white_point'])
        self.wpp_scale.bind('<ButtonRelease-1>', self.set_white_point)
        self.wpp_spin = ttk.Spinbox(exposureControls, from_=-100, to=100, increment=5, textvariable=self.white_point, width=5, command=self.set_white_point, validate='key', validatecommand=(validation, '%P', '%W'))
        self.wpp_spin.grid(row=2, column=2, sticky=tk.W)
        self.wpp_spin.bind('<Return>', self.set_white_point)
        self.wpp_spin.bind('<FocusOut>', self.set_white_point)
        ttk.Label(exposureControls, text='Black Point:').grid(row=3, column=0, sticky=tk.E)
        self.black_point = tk.IntVar()
        self.black_point.set(self.global_settings['black_point'])
        self.bpp_scale = ttk.Scale(exposureControls, from_=-100, to=100, orient=tk.HORIZONTAL, command=lambda x:self.black_point.set(round(float(x)/5)*5), length=100, value=self.black_point.get())
        self.bpp_scale.grid(row=3, column=1, padx=2)
        self.bpp_scale.set(self.global_settings['black_point'])
        self.bpp_scale.bind('<ButtonRelease-1>', self.set_black_point)
        self.bpp_spin = ttk.Spinbox(exposureControls, from_=-100, to=100, increment=5, textvariable=self.black_point, width=5, command=self.set_black_point, validate='key', validatecommand=(validation, '%P', '%W'))
        self.bpp_spin.grid(row=3, column=2, sticky=tk.W)
        self.bpp_spin.bind('<Return>', self.set_black_point)
        self.bpp_spin.bind('<FocusOut>', self.set_black_point)
        ttk.Label(exposureControls, text='Gamma:').grid(row=4, column=0, sticky=tk.E)
        self.gamma = tk.IntVar()
        self.gamma.set(self.global_settings['gamma'])
        self.gamma_scale = ttk.Scale(exposureControls, from_=-100, to=100, orient=tk.HORIZONTAL, command=lambda x:self.gamma.set(round(float(x)/5)*5), length=100, value=self.gamma.get())
        self.gamma_scale.grid(row=4, column=1, padx=2)
        self.gamma_scale.set(self.global_settings['gamma'])
        self.gamma_scale.bind('<ButtonRelease-1>', self.set_gamma)
        self.gamma_spin = ttk.Spinbox(exposureControls, from_=-100, to=100, increment=5, textvariable=self.gamma, width=5, command=self.set_gamma, validate='key', validatecommand=(validation, '%P', '%W'))
        self.gamma_spin.grid(row=4, column=2, sticky=tk.W)
        self.gamma_spin.bind('<Return>', self.set_gamma)
        self.gamma_spin.bind('<FocusOut>', self.set_gamma)
        ttk.Label(exposureControls, text='Shadows:').grid(row=5, column=0, sticky=tk.E)
        self.shadows = tk.IntVar()
        self.shadows.set(self.global_settings['shadows'])
        self.shad_scale = ttk.Scale(exposureControls, from_=-100, to=100, orient=tk.HORIZONTAL, command=lambda x:self.shadows.set(round(float(x)/5)*5), length=100, value=self.shadows.get())
        self.shad_scale.grid(row=5, column=1, padx=2)
        self.shad_scale.set(self.global_settings['shadows'])
        self.shad_scale.bind('<ButtonRelease-1>', self.set_shadows)
        self.shad_spin = ttk.Spinbox(exposureControls, from_=-100, to=100, increment=5, textvariable=self.shadows, width=5, command=self.set_shadows, validate='key', validatecommand=(validation, '%P', '%W'))
        self.shad_spin.grid(row=5, column=2, sticky=tk.W)
        self.shad_spin.bind('<Return>', self.set_shadows)
        self.shad_spin.bind('<FocusOut>', self.set_shadows)
        ttk.Label(exposureControls, text='Highlights:').grid(row=6, column=0, sticky=tk.E)
        self.highlights = tk.IntVar()
        self.highlights.set(self.global_settings['highlights'])
        self.high_scale = ttk.Scale(exposureControls, from_=-100, to=100, orient=tk.HORIZONTAL, command=lambda x:self.highlights.set(round(float(x)/5)*5), length=100, value=self.highlights.get())
        self.high_scale.grid(row=6, column=1, padx=2)
        self.high_scale.set(self.global_settings['highlights'])
        self.high_scale.bind('<ButtonRelease-1>', self.set_highlights)
        self.high_spin = ttk.Spinbox(exposureControls, from_=-100, to=100, increment=5, textvariable=self.highlights, width=5, command=self.set_highlights, validate='key', validatecommand=(validation, '%P', '%W'))
        self.high_spin.grid(row=6, column=2, sticky=tk.W)
        self.high_spin.bind('<Return>', self.set_highlights)
        self.high_spin.bind('<FocusOut>', self.set_highlights)

        # Export photo settings
        export_title = ttk.Label(text='Export Settings', font=self.header_style, padding=2)
        export_frame = ttk.LabelFrame(dynamic_scroll_frame.frame, borderwidth=2, labelwidget=export_title, padding=5)
        export_frame.grid(row=9, column=0, sticky='EW')
        export_settings_frame = ttk.Frame(export_frame)
        export_settings_frame.pack(fill='x')
        ttk.Label(export_settings_frame, text='Export File Type:', anchor='w').grid(row=0, column=0, sticky=tk.E)
        self.filetype_Combo = ttk.Combobox(export_settings_frame, state='readonly', values=self.filetypes, width=15)
        self.filetype_Combo.current(2)
        self.filetype_Combo.grid(row=0, column=1, sticky=tk.W, padx=2, columnspan=2)
        ttk.Label(export_settings_frame, text='White Frame (%):', anchor='w').grid(row=1, column=0, sticky=tk.E)
        self.frame = tk.IntVar()
        self.frame.set(raw_processing.frame)
        self.frame_scale = ttk.Scale(export_settings_frame, from_=0, to=10, orient=tk.HORIZONTAL, command=lambda x:self.frame.set(round(float(x))), length=100, value=self.frame.get())
        self.frame_scale.grid(row=1, column=1, sticky=tk.W, pady=5, padx=2)
        self.frame_scale.set(self.frame.get())
        self.frame_scale.bind('<ButtonRelease-1>', self.set_frame)
        frame_spin = ttk.Spinbox(export_settings_frame, from_=0, to=10, increment=1, textvariable=self.frame, validate='key', validatecommand=(validation, '%P', '%W'), command=self.set_frame, width=5)
        frame_spin.grid(row=1, column=2, sticky=tk.W, pady=5)
        frame_spin.bind('<Return>', self.set_frame)
        frame_spin.bind('<FocusOut>', self.set_frame)
        ttk.Label(export_frame, text='Output Destination Folder:', anchor='w').pack(fill = 'x')
        self.destination_folder_text = tk.StringVar()
        self.destination_folder_text.set('No Destination Folder Specified')
        destination_lbl = ttk.Label(export_frame, textvariable=self.destination_folder_text, anchor='w', font=('Segoe UI', 9, 'italic'))
        destination_lbl.pack(fill = 'x')
        destination_lbl.bind('<Configure>', lambda e: destination_lbl.config(wraplength=destination_lbl.winfo_width()))
        ttk.Button(export_frame, text='Select Folder', command=self.select_folder).pack(side=tk.LEFT, padx=2, pady=5)
        self.current_photo_button = ttk.Button(export_frame, text='Export Current Photo', command=self.export, state=tk.DISABLED)
        self.current_photo_button.pack(side=tk.LEFT, padx=2, pady=5)
        self.all_photo_button = ttk.Button(export_frame, text='Export All Photos', command=lambda: self.export(len(self.photos)), state=tk.DISABLED)
        self.all_photo_button.pack(side=tk.LEFT, padx=2, pady=5)
        self.abort_button = ttk.Button(export_frame, text='Abort Export', command=self.abort)

        # Progress Bar
        self.progressFrame = ttk.Frame(dynamic_scroll_frame.frame, padding=2)
        self.progress_percentage = ttk.Label(self.progressFrame)
        self.progress_percentage.pack(side=tk.RIGHT, anchor='n')
        self.progress = tk.DoubleVar()
        self.progress.set(0)
        self.progress_bar = ttk.Progressbar(self.progressFrame, variable=self.progress)
        self.progress_bar.pack(fill='x')
        self.progress_msg = ttk.Label(self.progressFrame)
        self.progress_msg.pack(side=tk.LEFT)

        # Showing converted image preview and intermediary steps
        self.outputFrame = ttk.Frame(mainFrame)
        self.outputFrame.grid_rowconfigure(3, weight=1)
        self.outputFrame.grid_columnconfigure(0, weight=1)
        self.read_error_lbl = ttk.Label(mainFrame, text='Error: File could not be read', font=('Segoe UI', 20), justify="center", anchor='center')
        self.read_error_lbl.bind('<Configure>', lambda e: self.read_error_lbl.config(wraplength=self.read_error_lbl.winfo_width()))

        # Process showing
        process_select_Frame = ttk.Frame(self.outputFrame)
        process_select_Frame.grid(row=0, column=0, pady=3)
        process_select_Frame.grid_rowconfigure(0, weight=1)
        process_select_Frame.grid_columnconfigure(1, weight=1)
        ttk.Label(process_select_Frame, text='Show:').grid(row=0, column=0)
        self.photo_process_Combo = ttk.Combobox(process_select_Frame, state='readonly', values=self.photo_process_values)
        self.photo_process_Combo.current(0)
        self.photo_process_Combo.bind('<<ComboboxSelected>>', self.update_IMG)
        self.photo_process_Combo.grid(row=0, column=1, padx=2)
        self.process_photo_frame = tk.Frame(self.outputFrame, padx=3, pady=3)
        self.process_photo_frame.grid(row=1, column=0)
        self.process_photo = ttk.Label(self.process_photo_frame)
        self.process_photo.pack()

        # Converted Preview
        ttk.Label(self.outputFrame, text='Preview:', font=self.header_style).grid(row=2, column=0)
        self.result_photo_frame = tk.Frame(self.outputFrame, padx=3, pady=3)
        self.result_photo_frame.grid(row=3, column=0)
        self.result_photo = ttk.Label(self.result_photo_frame)
        self.result_photo.pack()

        master.bind('<Configure>', self.resize_event)
        master.bind('<Key>', self.key_handler)
        master.bind('<Button>', self.click)
        master.protocol('WM_DELETE_WINDOW', self.on_closing)
        dynamic_scroll_frame.update()

        self.set_disable_buttons()
        try:
            params_dict = np.load('config.npy', allow_pickle=True).item()
        except:
            pass
        else:
            for object in [self, raw_processing]:
                for attr in object.advanced_attrs:
                    if attr in params_dict:
                        setattr(object, attr, params_dict[attr]) # Initializes every parameter with imported parameters
            

    def advanced_dialog(self):
        # Pop-up window to contain all the advanced settings that don't fit in the main controls
        class EntryLabel:
            # Defines custom widget with label with a spinbox next to it
            def __init__(widget, master, text, min, max, default_values, tkVar, increment=1, format='', width=10):
                nonlocal row
                def focus_in(variable):
                    widget.prev_value = variable.get() # when selected, store the current value for later

                def fix_num(variable):
                    # Keeps the input numeric and in-bounds
                    try:
                        variable.get()
                    except tk.TclError:
                        variable.set(widget.prev_value)
                    else:
                        if not is_float:
                            variable.set(round(variable.get()))
                        if variable.get() < min:
                            variable.set(min)
                        elif variable.get() > max:
                            variable.set(max)
                        widget.prev_value = variable.get()
                    top.focus()

                def numeric(input):
                    # validates the input as numeric and in bounds
                    try:
                        x = float(input)
                    except ValueError:
                        return False
                    else:
                        if not input.isnumeric() and not is_float:
                            return False
                        elif x < min:
                            return False
                        elif x > max:
                            return False
                        else:
                            return True
                
                validation = top.register(numeric)
                widget.variables_list = []
                is_float = tkVar == tk.DoubleVar
                try:
                    iter(default_values)
                except TypeError:
                    default_values = [default_values]
                
                widget.label = ttk.Label(master, text=text)
                widget.label.grid(row=row, column=0, sticky=tk.E)
                widget.entryFrame = ttk.Frame(master, width=20)
                widget.entryFrame.grid(row=row, column=1, sticky='new', padx=5, pady=2)
                widget.entryFrame.columnconfigure(0, weight=1)
                for i, value in enumerate(default_values):
                    variable = tkVar()
                    variable.set(value)
                    widget.variables_list.append(variable)
                    invalid = top.register(lambda: fix_num(variable))
                    spinbox = ttk.Spinbox(widget.entryFrame, textvariable=variable, from_=min, to=max, increment=increment, validate='focusout', validatecommand=(validation, '%P'), invalidcommand=invalid, format=format, width=width)
                    spinbox.grid(row=0, column=i, sticky='new')
                    spinbox.bind('<Return>', lambda x: fix_num(variable))
                    spinbox.bind('<FocusIn>', lambda x:focus_in(variable))
                row += 1
            def get(widget):
                # Returns the value of the entry
                output = tuple([var.get() for var in widget.variables_list])
                if len(output) == 1:
                    return output[0]
                else:
                    return output
            
            def show(widget):
                widget.label.grid(row=row, column=0, sticky=tk.E)
                widget.entryFrame.grid(row=row, column=1, sticky='new', padx=5, pady=2)
            
            def hide(widget):
                widget.label.grid_forget()
                widget.entryFrame.grid_forget()
        
        class ComboLabel:
            # Defines custom widget with a label and a dropdown menu next to it
            def __init__(widget, master, text, values, variable):
                nonlocal row
                ttk.Label(master, text=text).grid(row=row, column=0, sticky=tk.E)
                ttk.Combobox(master, textvariable=variable, values=values, state='readonly').grid(row=row, column=1, sticky='new', padx=5, pady=2)
                row += 1
        
        class CheckLabel:
            # Defines custom widget with a label and checkbox
            def __init__(widget, master, text, value, command):
                widget.variable = tk.BooleanVar()
                widget.variable.set(value)
                ttk.Label(master, text=text).grid(row=row, column=0, sticky=tk.E)
                ttk.Checkbutton(master, variable=widget.variable, command=command).grid(row=row, column=1, sticky='new', padx=5, pady=2)

            def get(widget):
                return widget.variable.get()
        
        def set_wb():
            # Hides or shows wb multipliers if using wb from camera
            if use_camera_wb.get():
                wb_mult.hide()
            else:
                wb_mult.show()

        def apply_settings():
            raw_processing.max_proxy_size = max_proxy_size.get()
            raw_processing.jpg_quality = jpg_quality.get()
            raw_processing.dm_alg = allowable_dm_algs[dm_algs_list.index(dm_alg.get())]
            raw_processing.colour_space = cs_list.index(colour_space.get())
            raw_processing.tiff_compression = t_comp_dict[tiff_compression.get()]
            raw_processing.exp_shift = exp_shift.get()
            raw_processing.fbdd_nr = fbdd_nr_list.index(fbdd_nr.get())
            raw_processing.raw_gamma = raw_gamma.get()
            raw_processing.use_camera_wb = use_camera_wb.get()
            raw_processing.wb_mult = list(wb_mult.get())
            raw_processing.white_point_percentile = white_point_percentile.get()
            raw_processing.black_point_percentile = black_point_percentile.get()
            raw_processing.ignore_border = ignore_border.get()
            raw_processing.dust_threshold = dust_threshold.get()
            raw_processing.dust_iter = dust_iter.get()
            raw_processing.max_dust_area = max_dust_area.get()
            self.max_processors_override = max_processors.get()
            self.preload = preload.get()
            
            quit()
            for photo in self.photos:
                photo.clear_memory()
            self.load_IMG()
        
        def save_settings():
            # saves the advanced settings as a config.npy file
            apply_settings()
            params_dict = dict()
            for attr in raw_processing.advanced_attrs:
                params_dict[attr] = getattr(raw_processing, attr)
            for attr in self.advanced_attrs:
                params_dict[attr] = getattr(self, attr)
            np.save('config.npy', params_dict)
        
        def quit():
            root.attributes('-disabled', 0)
            top.destroy()

        top = tk.Toplevel(root)
        top.transient(root)
        top.title('Advanced Settings')
        top.grab_set()
        top.bind('<Button>', lambda event: event.widget.focus_set())
        top.resizable(False, False)
        top.focus_set()
        top.transient(root)
        top.protocol('WM_DELETE_WINDOW', quit)
        root.attributes('-disabled', 1)

        mainFrame = ttk.Frame(top, padding=10)
        mainFrame.pack(fill='x')
        firstColumn = ttk.Frame(mainFrame, padding=2)
        firstColumn.grid(row=0, column=0, sticky='n')
        import_lbl = ttk.Label(top, text='Import:', font=self.header_style, padding=2)
        import_settings = ttk.LabelFrame(firstColumn, borderwidth=2, labelwidget=import_lbl, padding=5)
        import_settings.pack(fill='x', expand=True)
        export_lbl = ttk.Label(top, text='Export:', font=self.header_style, padding=2)
        export_settings = ttk.LabelFrame(firstColumn, borderwidth=2, labelwidget=export_lbl, padding=5)
        export_settings.pack(fill='x', expand=True)
        secondColumn = ttk.Frame(mainFrame, padding=2)
        secondColumn.grid(row=0, column=1, sticky='n')
        process_lbl = ttk.Label(top, text='Processing:', font=self.header_style, padding=2)
        process_settings = ttk.LabelFrame(secondColumn, borderwidth=2, labelwidget=process_lbl, padding=5)
        process_settings.pack(fill='x', expand=True)
        dust_lbl = ttk.Label(top, text='Dust Removal:', font=self.header_style, padding=2)
        dust_settings = ttk.LabelFrame(secondColumn, borderwidth=2, labelwidget=dust_lbl, padding=5)
        dust_settings.pack(fill='x', expand=True)

        row = 0 # starting row

        # Building pop-up GUI
        dm_alg = tk.StringVar()
        allowable_dm_algs = (0, 1, 2, 3, 4, 11, 12)
        dm_algs_list = ('LINEAR','VNG','PPG','AHD','DCB','DHT','AAHD')
        dm_alg.set(dm_algs_list[allowable_dm_algs.index(raw_processing.dm_alg)])
        ComboLabel(import_settings, 'Demosaicing Algorithm:', dm_algs_list, dm_alg)

        colour_space = tk.StringVar()
        cs_list = ('raw','sRGB','Adobe','Wide','ProPhoto','XYZ','ACES','P3D65','Rec2020')
        colour_space.set(cs_list[raw_processing.colour_space])
        ComboLabel(import_settings, 'RAW Output Colour Space:', cs_list, colour_space)

        raw_gamma = EntryLabel(import_settings, 'RAW Gamma (Power, Slope):', 0, 8, raw_processing.raw_gamma, tk.DoubleVar, 0.1, width=10)

        exp_shift = EntryLabel(import_settings, 'RAW Exposure Shift:', -2, 3, raw_processing.exp_shift, tk.IntVar)

        fbdd_nr = tk.StringVar()
        fbdd_nr_list = ('Off','Light','Full')
        fbdd_nr.set(fbdd_nr_list[raw_processing.fbdd_nr])
        ComboLabel(import_settings, 'FBDD Noise Reduction:', fbdd_nr_list, fbdd_nr)

        use_camera_wb = CheckLabel(import_settings, 'Use Camera White Balance:', raw_processing.use_camera_wb, set_wb)

        try:
            wb_lbl = 'White Balance Multipliers (' + self.current_photo.colour_desc + '):'
        except:
            wb_lbl = 'White Balance Multipliers:'
        wb_mult = EntryLabel(import_settings, wb_lbl, 0, 4, raw_processing.wb_mult, tk.DoubleVar, 0.1, width=4)
        set_wb()

        max_proxy_size = EntryLabel(process_settings, 'Max Proxy Size (W + H):', 500, 20000, raw_processing.max_proxy_size, tk.IntVar, 500)

        preload = EntryLabel(process_settings, 'Photo Preload Buffer Size:', 0, 20, self.preload, tk.IntVar)

        ignore_border = EntryLabel(process_settings, 'EQ Ignore Borders % (W, H):', 0, 40, raw_processing.ignore_border, tk.IntVar)

        white_point_percentile = EntryLabel(process_settings, 'White Point Percentile:', 70, 100, raw_processing.white_point_percentile, tk.DoubleVar)

        black_point_percentile = EntryLabel(process_settings, 'Black Point Percentile:', 0, 30, raw_processing.black_point_percentile, tk.DoubleVar)

        dust_threshold = EntryLabel(dust_settings, 'Threshold:', 0, 50, raw_processing.dust_threshold, tk.IntVar)

        dust_iter = EntryLabel(dust_settings, 'Noise Closing Iterations:', 1, 10, raw_processing.dust_iter, tk.IntVar)

        max_dust_area = EntryLabel(dust_settings, 'Max Particle Area:', 0, 100, raw_processing.max_dust_area, tk.IntVar)

        jpg_quality = EntryLabel(export_settings, 'JPEG Quality:', 0, 100, raw_processing.jpg_quality, tk.IntVar, 10)

        tiff_compression = tk.StringVar()
        t_comp_dict = {
            'No Compression': 1,
            'Lempel-Ziv & Welch': 5,
            'Adobe Deflate (ZIP)': 8,
            'PackBits': 32773
            }
        tiff_compression.set(list(t_comp_dict.keys())[list(t_comp_dict.values()).index(raw_processing.tiff_compression)])
        ComboLabel(export_settings, 'TIFF Compression:', list(t_comp_dict), tiff_compression)

        max_processors = EntryLabel(export_settings, 'Max Processors Override:', 0, multiprocessing.cpu_count(), self.max_processors_override, tk.IntVar)

        buttonFrame = ttk.Frame(mainFrame)
        buttonFrame.grid(row=1, column=0, columnspan=2, sticky='e')
        ttk.Button(buttonFrame, text='Cancel', command=quit).pack(side=tk.RIGHT, padx=2, pady=5, anchor='sw')
        ttk.Button(buttonFrame, text='Save', command=save_settings).pack(side=tk.RIGHT, padx=2, pady=5, anchor='sw')

        # Centres pop-up window over root window
        top.update_idletasks()
        x = root.winfo_x() + int((root.winfo_width()/2) - (top.winfo_width()/2))
        y = root.winfo_y() + int((root.winfo_height()/2) - (top.winfo_height()/2))
        top.geometry('+%d+%d' % (x, y))

    def validate(self, input, widget):
        # Validates if the input is numeric
        def set_value(value):
            # Function to replace value in current widget
            root.nametowidget(widget).delete(0,'end')
            root.nametowidget(widget).insert(0, value)
        if input == '' or input == '-':
            set_value(0)
        elif input == '0-':
            set_value('-0') # allows negative numbers to be more easily entered
        try: 
            int(input)
        except ValueError:
            return False # input is non-numeric
        else:
            # Get rid of leading zeros
            if input[0] == '0':
                set_value(input[1:])
            elif (input[:2] == '-0') and (len(input) > 2):
                set_value('-' + input[2:])
            return True
    
    def import_photos(self):
        # Import photos: opens dialog to load files, and intializes GUI
        if len(self.photos) > 0:
            if self.ask_save_settings() == None:
                return
            
        if hasattr(self, 'export_thread') and self.export_thread.is_alive():
            return # don't run if the export is running
            
        filenames = filedialog.askopenfilenames(title='Select RAW File(s)', filetypes=self.allowable_image_filetypes) # show an 'Open' dialog box and return the path to the selected files
        if len(filenames) == 0:
            return # if user clicks 'cancel', abort operation
        
        self.show_progress('Initializing import...') # display progress opening
        self.import_button.configure(state=tk.DISABLED)
        self.filemenu.entryconfigure('Import...', state=tk.DISABLED)
        
        total = len(filenames)
        self.photos = []
        photo_names = []
        
        self.update_progress(20, 'Initializing ' + str(total) + ' photos...')
        for i, filename in enumerate(filenames):
            photo = raw_processing(filename)
            self.photos.append(photo)
            photo_names.append(str(i + 1) + '. ' + str(photo))
        
        self.update_progress(80, 'Configuring GUI...')
        self.photoCombo.configure(values=photo_names) # configures dropdown to include list of photos
        self.photoCombo.current(0) # select the first photo to display

        self.update_progress(90, 'Loading photo...')
        self.load_IMG() # configure GUI to display the first photo
        self.update_progress(99)
        self.import_button.configure(state=tk.NORMAL)
        self.filemenu.entryconfigure('Import...', state=tk.NORMAL)
        self.update_UI()
        if self.glob_check.get() and self.global_settings != self.default_settings: # check if global settings are different from default on import
            self.unsaved = True # if it is the default, then it doesn't need to be saved
        else:
            self.unsaved = False
        self.hide_progress()
    
    def load_IMG(self, event=None):
        # Loading new image into GUI, loads other images in background
        def get_async_result(results, pool):
            attrs = ['RAW_IMG','memory_alloc','reject','FileReadError']
            for i, result in results:
                new_photo = result.get()
                for attr in attrs:
                    if hasattr(new_photo, attr):
                        setattr(self.photos[i], attr, getattr(new_photo, attr))
                self.in_progress.remove(i)
            pool.close()
        if len(self.photos) == 0:
            return
        photo_index = self.photoCombo.current()
        self.current_photo = self.photos[photo_index]
        self.glob_check.set(self.current_photo.use_global_settings)
        if self.current_photo.use_global_settings:
            self.apply_settings(self.current_photo, self.global_settings)
        self.change_settings() # Ensures that the GUI matches the photo's parameters
        if not self.current_photo.processed:
            self.current_photo.process() # only process photos if needed
        self.update_IMG()

        # conservatively load extra images in background to speed up switching, while saving memory
        results = []
        pool = multiprocessing.Pool(4)
        for i, photo in enumerate(self.photos):
            if (abs(i - photo_index) <= self.preload) and not hasattr(photo, 'RAW_IMG') and i not in self.in_progress: # preload photos in buffer ahead or behind of the currently selected one
                result = pool.apply_async(load_photo, (photo,))
                results.append((i, result))
                self.in_progress.add(i) # keeps track of photos in progress
            elif (abs(i - photo_index) > self.preload) and hasattr(photo, 'RAW_IMG'): # delete photos outside of buffer
                photo.clear_memory()
        
        threading.Thread(target=get_async_result, args=(results, pool), daemon=True).start() # retrieve images from multiprocessing when done

        self.set_disable_buttons()
    
    def update_IMG(self, full_res=True):
        # Loads new image into GUI
        # Queues full res picture to be loaded when ignore_full_res is set to False and the Full Preview is selected (default behaviour)
        def update_full_res():
            # Checks periodically if the thread is finished, then updates the image
            def check_if_done(t):
                if not t.is_alive():
                    if not self.current_photo.active_processes:
                        self.update_IMG(False) # update image, but do not queue full res process again
                else:
                    root.after(300, check_if_done, t) # if not done, wait some time, then check again
            t = threading.Thread(target=self.current_photo.process, args=[True, True, True], daemon=True) # Thread to generate full res previews
            t.start()
            root.after_idle(check_if_done, t)
        if len(self.photos) == 0:
            return
        try:
            if self.current_photo.get_IMG() == None:
                raise Exception
        except Exception as e:
            print(e)
            self.outputFrame.grid_forget()
            self.read_error_lbl.grid(row=0, column=1, sticky='EW') # displays error message when image cannot be loaded
            return
        
        self.read_error_lbl.grid_forget()
        self.outputFrame.grid(row=0, column=1, sticky='NSEW')
        if self.photo_process_Combo.current() == 4: # if "Full Preview" is selected
            self.process_photo_frame.grid_forget() # hide the process photo
            self.photo_display_height = max(int(root.winfo_height() - 100), 100) # resize image to full display height
        else:
            self.photo_display_height = max(int((root.winfo_height() - 100) / 2), 100)
            process_photo = ImageTk.PhotoImage(self.resize_IMG(self.current_photo.get_IMG(self.photo_process_values[self.photo_process_Combo.current()])))
            self.process_photo.configure(image=[process_photo])
            self.process_photo.image = process_photo
            self.process_photo_frame.grid(row=1, column=0)

        result_photo = ImageTk.PhotoImage(self.resize_IMG(self.current_photo.get_IMG()))
        self.result_photo.configure(image=[result_photo])
        self.result_photo.image = result_photo
        root.update()

        if full_res:
            # Generates full resolution image in the background
            if self.photo_process_Combo.current() == 4: # Only display when full preview is selected
                try: root.after_cancel(self.start_full_res)
                except: pass
                finally: self.start_full_res = root.after(500, update_full_res) # waits for 0.5 s of inactivity before processing

    def resize_IMG(self, img):  
        # Resizes the displayed image based on maximum allowable dimensions, while maintaining aspect ratio
        w, h = img.size
        scale = min(self.photo_display_width / w, self.photo_display_height / h)
        new_img = img.resize((int(w * scale), int(h * scale)))
        return new_img
    
    def resize_event(self, event=None):
        # Attempts to resize the images if the resize event has not been called for 100 ms
        try:
            root.after_cancel(self.resize)
        except:
            pass
        finally:
            self.resize = root.after(100, self.resize_UI)
    
    def resize_UI(self):
        # Calculates the maximum dimensions for the displayed images based on the size of the window
        self.photo_display_width = max(int(root.winfo_width() - self.controlsFrame.winfo_width() - 20), 100)
        if self.photo_process_Combo.current() == 4:
            self.photo_display_height = max(int(root.winfo_height() - 100), 100)
        else:
            self.photo_display_height = max(int((root.winfo_height() - 100) / 2), 100)
        self.update_IMG(False)
    
    def previous(self):
        # Previous button
        if len(self.photos) == 0:
            return
        i = self.photoCombo.current()
        if i > 0:
            self.photoCombo.current(i - 1)
            self.load_IMG()
        self.set_disable_buttons()
    
    def next(self):
        # Next button
        if len(self.photos) == 0:
            return
        i = self.photoCombo.current()
        if i < len(self.photos) - 1:
            self.photoCombo.current(i + 1)
            self.load_IMG()
        self.set_disable_buttons()
    
    def set_disable_buttons(self):
        # Configures enable/disable states of next/previous buttons
        i = self.photoCombo.current()
        if i <= 0:
            self.prevButton.configure(state=tk.DISABLED)
        else:
            self.prevButton.configure(state=tk.NORMAL)
        if i + 1 >= len(self.photos):
            self.nextButton.configure(state=tk.DISABLED)
        else:
            self.nextButton.configure(state=tk.NORMAL)

    def set_reject(self, event=None):
        # Defines behaviour of the 'Discard' checkbox
        if len(self.photos) > 0:
            self.current_photo.reject = self.reject_check.get()
        self.update_UI()
        self.unsaved = True

    def set_global(self, event=None):
        # Defines behaviour of the 'Use Global Settings' checkbox
        if len(self.photos) == 0:
            return
        self.current_photo.use_global_settings = self.glob_check.get()
        self.apply_settings(self.current_photo, self.global_settings)
        self.change_settings()
        self.unsaved = True
        if self.glob_check.get():
            self.current_photo.process()
            self.update_IMG()

    def change_settings(self, reset=False):
        # Configures GUI to reflect current applied settings for the photo
        self.reject_check.set(self.current_photo.reject)

        if self.current_photo.FileReadError:
            self.reject_CheckButton.configure(state=tk.DISABLED)
        else:
            self.reject_CheckButton.configure(state=tk.NORMAL)
        
        self.filmCombo.current(self.current_photo.film_type)

        self.dust_check.set(self.current_photo.remove_dust)

        self.dark_threshold.set(self.current_photo.dark_threshold)
        self.dark_threshold_scale.set(self.current_photo.dark_threshold)

        self.light_threshold.set(self.current_photo.light_threshold)
        self.light_threshold_scale.set(self.current_photo.light_threshold)

        self.border_crop.set(self.current_photo.border_crop)
        self.bc_scale.set(self.current_photo.border_crop)

        self.flip_check.set(self.current_photo.flip)

        self.white_point.set(self.current_photo.white_point)
        self.wpp_scale.set(self.current_photo.white_point)

        self.black_point.set(self.current_photo.black_point)
        self.bpp_scale.set(self.current_photo.black_point)

        self.gamma.set(self.current_photo.gamma)
        self.gamma_scale.set(self.current_photo.gamma)

        self.shadows.set(self.current_photo.shadows)
        self.shad_scale.set(self.current_photo.shadows)

        self.highlights.set(self.current_photo.highlights)
        self.high_scale.set(self.current_photo.highlights)

        self.temp.set(self.current_photo.temp)
        self.temp_scale.set(self.current_photo.temp)

        self.tint.set(self.current_photo.tint)
        self.tint_scale.set(self.current_photo.tint)
        
        self.sat.set(self.current_photo.sat)
        self.sat_scale.set(self.current_photo.sat)

        self.base.current(self.current_photo.base_detect)
        self.base_rgb.set(str(self.current_photo.base_rgb)) 
        self.rgb_display.configure(bg=self._from_rgb(self.current_photo.base_rgb))

        self.update_UI()

    def apply_settings(self, photo, settings):
        # applies settings to photo based on input dictionary containing settings
        for attribute in settings.keys():
            setattr(photo, attribute, settings[attribute])
    
    def changed_global_settings(self):
        # sets flags of all photos using global settings to be unprocessed when global settings are changed
        if len(self.photos) == 0:
            return
        for photo in self.photos:
            if photo.use_global_settings:
                photo.processed = False

    def reset_settings(self):
        # Reset settings to default parameters
        if len(self.photos) == 0:
            return
        if self.glob_check.get():
            affected = sum([photo.use_global_settings for photo in self.photos]) # calculate the total number of photos using global settings
            if affected > 1:
                if not messagebox.askyesno('Reset to Default Settings','You are about to globally reset ' + str(affected) + ' photos\'s settings.\nDo you wish to continue?', icon='warning'):
                    return
            self.global_settings = self.default_settings.copy() # reset global settings
            self.changed_global_settings()
        self.apply_settings(self.current_photo, self.default_settings) # apply new settings to photo
        self.change_settings() # update GUI with new settings
        self.current_photo.process()
        self.update_IMG()
        self.unsaved = True
    
    # The following functions all define the behaviour of the interactable GUI, such as buttons, entries, and scales

    def set_film_type(self, event=None):
        if self.glob_check.get():
            self.global_settings['film_type'] = self.filmCombo.current()
            self.changed_global_settings()
        self.update_UI()
        if len(self.photos) == 0:
            return
        self.current_photo.film_type = self.filmCombo.current()
        self.current_photo.process()
        self.update_IMG()
        self.unsaved = True
    
    def update_UI(self):
        # Changes which settings are visible
        if (self.filmCombo.current() == 3) or self.reject_check.get():
            self.exposureFrame.grid_forget() # Hide the exposure frame when set to output RAW
        else:
            self.exposureFrame.grid(row=7, column=0, sticky='EW')

        if ((self.filmCombo.current() == 1) or (self.filmCombo.current() == 2)) and not self.reject_check.get():
            self.colourFrame.grid(row=6, column=0, sticky='EW') # Show the colour frame only for colour and slides
        else:
            self.colourFrame.grid_forget()
        
        if self.reject_check.get():
            self.cropFrame.grid_forget()
            self.globFrame.grid_forget()
            self.filmFrame.grid_forget()
            self.dustFrame.grid_forget()
            self.editmenu.entryconfigure('Reset to Default Settings', state=tk.DISABLED)
        else:
            self.cropFrame.grid(row=4, column=0, sticky='EW')
            self.globFrame.grid(row=1, column=0, sticky='EW')
            self.filmFrame.grid(row=3, column=0, sticky='EW')
            self.dustFrame.grid(row=4, column=0, sticky='EW')
            self.editmenu.entryconfigure('Reset to Default Settings', state=tk.NORMAL)
        
        if self.reject_check.get() or len(self.photos) == 0:
            self.current_photo_button.configure(state=tk.DISABLED)
        else:
            self.current_photo_button.configure(state=tk.NORMAL)
        
        if len([photo for photo in self.photos if not photo.reject]) == 0:
            self.all_photo_button.configure(state=tk.DISABLED)
        else:
            self.all_photo_button.configure(state=tk.NORMAL)
        
        if self.base.current():
            self.base_clr_lbl.grid(row=1, column=0, sticky=tk.E)
            self.base_rgb_lbl.grid(row=1, column=1, sticky=tk.W)
            self.rgb_display.grid(row=1, column=2, sticky=tk.W)
            self.base_pick_button.grid(row=1, column=3, sticky=tk.W)
            self.base_buttons_frame.grid(row=2, column=0, columnspan=4, sticky='e')
        else:
            self.base_clr_lbl.grid_forget()
            self.base_rgb_lbl.grid_forget()
            self.rgb_display.grid_forget()
            self.base_pick_button.grid_forget()
            self.base_buttons_frame.grid_forget()
    
    def set_remove_dust(self, event=None):
        if self.glob_check.get():
            self.global_settings['remove_dust'] = self.dust_check.get()
            self.changed_global_settings()
        if len(self.photos) == 0:
            return
        self.current_photo.remove_dust = self.dust_check.get()
        self.update_IMG()
        self.unsaved = True
            
    def set_dark_threshold(self, event=None):
        if self.glob_check.get():
            self.global_settings['dark_threshold'] = self.dark_threshold.get()
            self.changed_global_settings()
        self.dark_threshold_scale.set(self.dark_threshold.get())
        if len(self.photos) == 0:
            return
        self.current_photo.dark_threshold = self.dark_threshold.get()
        self.current_photo.process()
        self.update_IMG()
        self.unsaved = True

    def set_light_threshold(self, event=None):
        if self.glob_check.get():
            self.global_settings['light_threshold'] = self.light_threshold.get()
            self.changed_global_settings()
        self.light_threshold_scale.set(self.light_threshold.get())
        if len(self.photos) == 0:
            return
        self.current_photo.light_threshold = self.light_threshold.get()
        self.current_photo.process()
        self.update_IMG()
        self.unsaved = True
    
    def set_border_crop(self, event=None):
        if self.glob_check.get():
            self.global_settings['border_crop'] = self.border_crop.get()
            self.changed_global_settings()
        self.bc_scale.set(self.border_crop.get())
        if len(self.photos) == 0:
            return
        self.current_photo.border_crop = self.border_crop.get()
        self.current_photo.process()
        self.update_IMG()
        self.unsaved = True
    
    def set_flip(self, event=None):
        if self.glob_check.get():
            affected = sum([photo.use_global_settings for photo in self.photos])
            if affected > 1:
                if messagebox.askyesno('Flip Photo', 'Do you want to globally flip ' + str(affected) + ' photos?', default='no'):
                    self.global_settings['flip'] = self.flip_check.get()
                    self.changed_global_settings()
                else:
                    self.glob_check.set(False)
                    self.current_photo.use_global_settings = False
            else:
                self.global_settings['flip'] = self.flip_check.get()
                self.changed_global_settings()
        if len(self.photos) == 0:
            return
        self.current_photo.flip = self.flip_check.get()
        self.update_IMG()
        self.unsaved = True
    
    def rot_clockwise(self, event=None):
        if len(self.photos) == 0:
            return
        if self.flip_check.get():
            self.current_photo.rotation -= 1
        else:
            self.current_photo.rotation += 1
        self.update_IMG()
        self.unsaved = True
    
    def rot_counterclockwise(self, event=None):
        if len(self.photos) == 0:
            return
        if self.flip_check.get():
            self.current_photo.rotation += 1
        else:
            self.current_photo.rotation -= 1
        self.update_IMG()
        self.unsaved = True
    
    def set_white_point(self, event=None):
        if self.glob_check.get():
            self.global_settings['white_point'] = self.white_point.get()
            self.changed_global_settings()
        self.wpp_scale.set(self.white_point.get())
        if len(self.photos) == 0:
            return
        self.current_photo.white_point = self.white_point.get()
        self.current_photo.process(skip_crop=True)
        self.update_IMG()
        self.unsaved = True
    
    def set_black_point(self, event=None):
        if self.glob_check.get():
            self.global_settings['black_point'] = self.black_point.get()
            self.changed_global_settings()
        self.bpp_scale.set(self.black_point.get())
        if len(self.photos) == 0:
            return
        self.current_photo.black_point = self.black_point.get()
        self.current_photo.process(skip_crop=True)
        self.update_IMG()
        self.unsaved = True

    def set_gamma(self, event=None):
        if self.glob_check.get():
            self.global_settings['gamma'] = self.gamma.get()
            self.changed_global_settings()
        self.gamma_scale.set(self.gamma.get())
        if len(self.photos) == 0:
            return
        self.current_photo.gamma = self.gamma.get()
        self.current_photo.process(skip_crop=True)
        self.update_IMG()
        self.unsaved = True
    
    def set_shadows(self, event=None):
        if self.glob_check.get():
            self.global_settings['shadows'] = self.shadows.get()
            self.changed_global_settings()
        self.shad_scale.set(self.shadows.get())
        if len(self.photos) == 0:
            return
        self.current_photo.shadows = self.shadows.get()
        self.current_photo.process(skip_crop=True)
        self.update_IMG()
        self.unsaved = True
    
    def set_highlights(self, event=None):
        if self.glob_check.get():
            self.global_settings['highlights'] = self.highlights.get()
            self.changed_global_settings()
        self.high_scale.set(self.highlights.get())
        if len(self.photos) == 0:
            return
        self.current_photo.highlights = self.highlights.get()
        self.current_photo.process(skip_crop=True)
        self.update_IMG()
        self.unsaved = True

    def pick_wb(self):
        # Enables the white balance picker and cursor
        if len(self.photos) == 0:
            return
        self.wb_picker_button.state(['pressed']) # keeps the button pressed
        self.result_photo.configure(cursor='tcross') # changes the cursor over the preview to a cross
        self.result_photo_frame.configure(background='red') # highlights the preview image
        self.wb_picker = True # flag to indicate that the wb picker is enabled

    def click(self, event):
        # Event handler for all clicks on GUI
        event.widget.focus_set() # if clicked anywhere, set focus to that widget
        if self.wb_picker and (event.widget != self.wb_picker_button):
            # Logic for if the white balance picker is selected
            self.wb_picker_button.state(['!pressed']) # reset button
            self.result_photo.configure(cursor='arrow') # reset cursor
            self.result_photo_frame.configure(background=root.cget('bg')) # reset frame
            self.wb_picker = False
            if event.widget == self.result_photo:
                x = event.x / event.widget.winfo_width()
                y = event.y / event.widget.winfo_height()
                self.current_photo.set_wb_from_picker(x, y) # set the white balance to neutral at the x, y cooredinates of the mouse click

                self.temp.set(self.current_photo.temp)
                self.temp_scale.set(self.current_photo.temp)

                self.tint.set(self.current_photo.tint)
                self.tint_scale.set(self.current_photo.tint)

                if self.glob_check.get():
                    affected = sum([photo.use_global_settings for photo in self.photos])
                    if affected > 1:
                        if messagebox.askyesno('White Balance Picker', 'Do you want to apply this white balance adjustment globally to ' + str(affected) + ' photos?', default='no'):
                            self.global_settings['temp'] = self.temp.get()
                            self.global_settings['tint'] = self.tint.get()
                            self.changed_global_settings()
                        else:
                            self.glob_check.set(False)
                            self.current_photo.use_global_settings = False
                    else:
                        self.global_settings['temp'] = self.temp.get()
                        self.global_settings['tint'] = self.tint.get()
                        self.changed_global_settings()

                self.update_IMG()
                self.unsaved = True
        elif self.base_picker and (event.widget != self.base_pick_button):
            # Logic for if the base picker is selected
            self.base_pick_button.state(['!pressed']) # reset button
            self.process_photo.configure(cursor='arrow') # reset cursor
            self.process_photo_frame.configure(background=root.cget('bg')) # reset frane
            self.base_picker = False
            if event.widget == self.process_photo:
                x = event.x / event.widget.winfo_width()
                y = event.y / event.widget.winfo_height()
                self.current_photo.get_base_colour(x,y) # retrieve base colour at the x, y coordinates of the mouse click
                self.set_base_rgb(1)

    def set_base_detect(self, event=None):
        # Switches between auto base colour detect and manual setting
        if self.glob_check.get():
            affected = sum([photo.use_global_settings for photo in self.photos])
            if affected > 1:
                if messagebox.askyesno('Base Colour Changed', 'Do you want change the base colour globally to ' + str(affected) + ' photos?', default='no'):
                    self.global_settings['base_detect'] = self.base.current()
                    self.changed_global_settings()
                else:
                    self.glob_check.set(False)
                    self.current_photo.use_global_settings = False
            else:
                self.global_settings['base_detect'] = self.base.current()
                self.changed_global_settings()
        self.update_UI()
        if len(self.photos) == 0:
            return
        self.current_photo.base_detect = self.base.current()
        self.current_photo.process(skip_crop=True)
        self.update_IMG()
        self.unsaved = True

    # logic to get the base rgb value, and configure the GUI accordingly
    def set_base_rgb(self, mode):
        match mode:
            case 0: # set rgb from colour picker
                try:
                    colour = self.current_photo.base_rgb
                except:
                    colour = None
                rgb, _ = colorchooser.askcolor(colour, title='Enter Film Base RGB')
                if rgb == None:
                    return
            case 1: # pick colour from RAW image
                rgb = self.current_photo.base_rgb
            case 2: # pick colour from blank scan
                filename = filedialog.askopenfile(title='Select Blank Film Scan', filetypes=self.allowable_image_filetypes)
                try:
                    filename = filename.name
                except:
                    return
                try:
                    with rawpy.imread(filename) as raw: # tries to read as raw file
                        raw_img = raw.postprocess(
                            output_bps = 8, # output 8-bit image
                            use_camera_wb = raw_processing.use_camera_wb, # Screws up the colours if not used
                            user_wb = raw_processing.wb_mult, # wb multipliers
                            demosaic_algorithm = rawpy.DemosaicAlgorithm(raw_processing.dm_alg),
                            output_color = rawpy.ColorSpace(raw_processing.colour_space),
                            gamma = raw_processing.raw_gamma, # Guessed random numbers, these seemed to work the best
                            auto_bright_thr = 0, # no clipping of highlights
                            exp_preserve_highlights = 1,
                            exp_shift = 2 ** raw_processing.exp_shift,
                            half_size = True # take the average of 4 pixels to reduce resolution
                            )
                except:
                    try:
                        raw_img = cv2.imread(filename) # if fails, reads as normal image
                        if type(raw_img) != np.ndarray:
                            raise Exception
                        raw_img = raw_img[:,:,::-1] # converts BGR to RGB
                    except: # If fails again, generate error message
                        messagebox.showerror('Error: File Read Error','The selected image could not be read.')
                        return
                brightness = np.sum(raw_img.astype(np.uint16), 2)
                sample = np.percentile(brightness, 90) # take sample at 90th percentile brightest pixel
                index = np.where(brightness==sample)
                rgb = raw_img[index[0][0]][index[1][0]]
                rgb = tuple(rgb.tolist())

        if self.glob_check.get():
            self.global_settings['base_rgb'] = rgb
            self.changed_global_settings()
        self.base_rgb.set(str(rgb)) 
        self.rgb_display.configure(bg=self._from_rgb(rgb))
        if len(self.photos) == 0:
            return
        self.current_photo.base_rgb = rgb
        self.current_photo.process(skip_crop=True)
        self.update_IMG()
        self.unsaved = True
    
    def set_base(self):
        # enables the base colour picker
        if len(self.photos) == 0:
            return
        self.base_pick_button.state(['pressed']) # keeps the button pressed
        self.process_photo.configure(cursor='tcross') # changes the cursor over the preview to a cross
        self.photo_process_Combo.current(0) # display the RAW photo
        self.process_photo_frame.configure(background='red') # highlights the raw photo
        self.base_picker = True # flag to indicate that the wb picker is enabled
        self.update_IMG()

    def set_temp(self, event=None):
        if self.glob_check.get():
            self.global_settings['temp'] = self.temp.get()
            self.changed_global_settings()
        self.temp_scale.set(self.temp.get())
        if len(self.photos) == 0:
            return
        self.current_photo.temp = self.temp.get()
        self.current_photo.process(skip_crop=True)
        self.update_IMG()
        self.unsaved = True
    
    def set_tint(self, event=None):
        if self.glob_check.get():
            self.global_settings['tint'] = self.tint.get()
            self.changed_global_settings()
        self.tint_scale.set(self.tint.get())
        if len(self.photos) == 0:
            return
        self.current_photo.tint = self.tint.get()
        self.current_photo.process(skip_crop=True)
        self.update_IMG()
        self.unsaved = True

    def set_sat(self, event=None):
        if self.glob_check.get():
            self.global_settings['sat'] = self.sat.get()
            self.changed_global_settings()
        self.sat_scale.set(self.sat.get())
        if len(self.photos) == 0:
            return
        self.current_photo.sat = self.sat.get()
        self.current_photo.process(skip_crop=True)
        self.update_IMG()
        self.unsaved = True

    def set_frame(self, event=None):
        # Adds a decorative white border to final output
        if self.frame.get() > 10:
            self.frame.set(10)
        elif self.frame.get() < 0:
            self.frame.set(0)
        self.frame_scale.set(self.frame.get())
        raw_processing.frame = self.frame.get()
        self.update_IMG()
    
    def select_folder(self):
        # Dialog to select output destination folder
        self.destination_folder = filedialog.askdirectory() + '/' # opens dialog to choose folder
        if len(self.destination_folder) <= 1:
            return
        self.destination_folder_text.set(self.destination_folder) # display destination folder in GUI

    def export(self, n_photos=1):
        # Start export in seperate thread to keep UI responsive
        if len([photo for photo in self.photos if not photo.reject]) == 0:
            return
        if n_photos == 1:
            export_fn = self.export_individual
        else:
            export_fn = self.export_multiple
        
        self.export_thread = threading.Thread(target=export_fn, daemon=True)
        self.export_thread.start()
    
    def export_individual(self):
        # Exports only photo that is currently visible
        if len(self.photos) == 0:
            return
        
        self.show_progress() # display progress bar

        self.current_photo_button.configure(state=tk.DISABLED)
        self.all_photo_button.configure(state=tk.DISABLED)
        self.import_button.configure(state=tk.DISABLED)
        self.filemenu.entryconfigure('Import...', state=tk.DISABLED)
        
        self.update_progress(20, 'Processing...') # Arbitrary progress display
        self.current_photo.load(True)
        self.current_photo.process(True)
        self.update_progress(99, 'Exporting photo...')
        filename = self.destination_folder + str(self.current_photo).split('.')[0] # removes the file extension
        filename = filename + '.' + self.filetypes[self.filetype_Combo.current()]  # sets the file extension
        self.current_photo.export(filename) # saves the photo
        self.current_photo_button.configure(state=tk.NORMAL)
        self.all_photo_button.configure(state=tk.NORMAL)
        self.import_button.configure(state=tk.NORMAL)
        self.filemenu.entryconfigure('Import...', state=tk.NORMAL)
        self.hide_progress() # hide the progress bar
    
    def export_multiple(self):
        # This function exports all photos that are loaded. Uses multiprocessing to parallelize export.
        if len(self.photos) == 0:
            return
        self.show_progress('Applying photo settings...') # display progress bar
        self.current_photo_button.configure(state=tk.DISABLED)
        self.all_photo_button.pack_forget()
        self.abort_button.pack(side=tk.LEFT, padx=2, pady=5)
        self.import_button.configure(state=tk.DISABLED)
        self.filemenu.entryconfigure('Import...', state=tk.DISABLED)

        filetype = self.filetypes[self.filetype_Combo.current()] # sets the file type for export

        inputs = []
        allocated = 0 # sum of total allocated memory
        has_alloc = 0 # number of photos in which the memory allocation has been calculated
        
        with multiprocessing.Manager() as manager:
            self.terminate = manager.Event() # flag to abort export and safely close processes

            for photo in self.photos:
                if photo.reject:
                    continue
                if photo.use_global_settings:
                    self.apply_settings(photo, self.global_settings) # Ensures the proper settings have been applied
                filename = self.destination_folder + str(photo).split('.')[0] # removes the file extension
                filename = filename + '.' + filetype # creates file path with file name and extension
                inputs.append((photo, filename, self.terminate))
                if hasattr(photo, 'memory_alloc'):
                    allocated += photo.memory_alloc # tally of estimated memory requirements of each photo
                    has_alloc += 1
            
            if self.max_processors_override != 0:
                max_processors = self.max_processors_override
            else:
                # limting the maximum number of processes based on available system memory
                available = psutil.virtual_memory()[1]
                #print('Available system RAM for export:', round(available / 1e9,1),'GB')
                allocated = allocated / has_alloc # allocated memory as average of estimated memory requirements for each photo
                #print(round(allocated / 1e9,1),'GB allocated')
                max_processors = round(available / allocated)
            processes = max(min(max_processors, multiprocessing.cpu_count(), len(inputs)), 1) # allocates number of processors between 1 and the maximum number of processors available
            #print(processes, 'processes allocated for export')

            self.update_progress(20, 'Allocating ' + str(processes) + ' processor(s) for export...')
            with multiprocessing.Pool(processes) as self.pool:
                i = 1
                errors = []
                for error in self.pool.imap(export, inputs):
                    if self.terminate.is_set():
                        self.pool.terminate()
                        break
                    if error:
                        errors.append(error) # keeps track of any errors raised
                    update_message = 'Exported ' + str(i) + ' of ' + str(len(inputs)) + ' photos.'
                    self.update_progress(i / len(inputs) * 80 + 19.99, update_message) # update progress display
                    i += 1
        if errors and not self.terminate.is_set():
            # if errors are raised, display dialog with errors
            errors_display = 'Details:'
            for i, error in enumerate(errors, 1):
                errors_display += '\n' + str(i) + '. ' + str(error)
            messagebox.showerror('Export Error',str(len(errors)) + ' export(s) failed.\n' + errors_display)

        self.current_photo_button.configure(state=tk.NORMAL)
        self.abort_button.pack_forget()
        self.all_photo_button.pack(side=tk.LEFT, padx=2, pady=5)
        self.import_button.configure(state=tk.NORMAL)
        self.filemenu.entryconfigure('Import...', state=tk.NORMAL)
        self.hide_progress() # hide the progress bar

    def abort(self):
        # Stop the export
        try:
            self.terminate.set()
        except:
            pass
    
    # Defines how to show and hide the progress bar
    def show_progress(self, message=''):
        self.progressFrame.grid(row=10, column=0, sticky='EW')
        self.update_progress(0, message)
    
    def hide_progress(self):
        self.progressFrame.grid_forget()
    
    def update_progress(self, percentage, message=''):
        # takes number between 0 and 100 to display progress, with optional parameter to display message
        self.progress.set(percentage)
        self.progress_percentage.configure(text=str(round(percentage))+'%')
        self.progress_msg.configure(text=message)
        root.update()

    def key_handler(self, event):
        # Maps left and right arrow keys to show previous or next photo respectively
        match event.keysym:
            case 'Right':
                self.next()
            case 'Left':
                self.previous()
    
    def on_closing(self):
        # Behaviour/cleanup at closing
        if len(self.photos) > 0:
            if self.ask_save_settings() == None: # if "Cancel" is pressed, do nothing
                return
            
        if hasattr(self, 'export_thread') and self.export_thread.is_alive(): # check if the export thread is still alive
            if messagebox.askyesno(title='Export in Progress', icon='warning', message='Export is still in progress. Do you really want to quit?', default='no'):
                try:
                    self.pool.terminate()
                except:
                    pass
            else:
                return
        root.destroy() # quit program

    def ask_save_settings(self):
        # dialog to ask if settings are to be saved. If yes, saves settings and returns True. No returns False. Cancel returns None.
        if self.unsaved:
            result = messagebox.askyesnocancel('Unsaved Changes', 'Do you want to save the changes you made to this batch of photos?')
        else:
            return False
        if result:
            self.save_settings()
        return result
    
    def save_settings(self):
        # loops through all the photos and applies global settings where needed, then saves the settings to disk
        for photo in self.photos:
            if photo.use_global_settings:
                self.apply_settings(photo, self.global_settings) # apply most current settings before saving
            photo.save_settings()
        self.unsaved = False
    
    @staticmethod
    def _from_rgb(rgb):
        # translates an rgb tuple of int to a tkinter friendly color code
        return '#%02x%02x%02x' % rgb
    
# \/ Multiprocessing Functions \/
def load_photo(photo):
    for _ in range(5):
        try:
            photo.load() # load RAW file into memory
        except Exception as e:
            continue
        else:
            return photo
    print(e)

def export(inputs):
    photo, filename, terminate = inputs
    for _ in range(5):
        try:
            if terminate.is_set():
                return
            photo.load(True)
            if photo.FileReadError:
                raise Exception('File could not be read')
            if terminate.is_set():
                return
            photo.process(True) # process photo in full quality
        except Exception as e:
            error = e
        else:
            if terminate.is_set():
                return
            photo.export(filename)
            photo.clear_memory()
            return False
    return error

class raw_processing:
    # This class defines a photo object that contains the image processing pipeline from raw to final export, including all processing functions and parameters
    # Class variables (affects all photos)
    max_proxy_size = 2000 # Max dimension of height + width to increase processing speed (only for previews)
    histogram_plt_size = (1600, 2400, 3) # Dimensions of the histogram
    hist_bg_colour = (25, 25, 25) # sets the backgroud colour of the histogram
    frame = 0 # adds white frame to final photo
    jpg_quality = 90 # from 0-100
    tiff_compression = 8 # defines the tiff compression algorithm
    dm_alg = 2 # demosaicing algorithm
    colour_space = 7 # output colour space after demosaicing
    exp_shift = 3
    fbdd_nr = 0 # noise reduction on demosaic
    raw_gamma = (2.222,4.5) # (power, slope) for RAW image
    use_camera_wb = True
    wb_mult = [1, 1, 1, 1]
    black_point_percentile = 0 # sets the black point
    white_point_percentile = 99 # sets the default white balance as a percentile of the brightest pixels
    ignore_border = (1, 1) # ignores the border for calculation of histogram EQ
    dust_threshold = 10
    max_dust_area = 15
    dust_iter = 5
    advanced_attrs = ('max_proxy_size','jpg_quality','tiff_compression','dm_alg','colour_space','exp_shift','fbdd_nr','raw_gamma','use_camera_wb','wb_mult', 'black_point_percentile', 'white_point_percentile','ignore_border','dust_threshold','max_dust_area','dust_iter')
    processing_parameters = ('dark_threshold','light_threshold','border_crop','flip','rotation','film_type','white_point','black_point','gamma','shadows','highlights','temp','tint','sat','reject','base_detect','base_rgb', 'remove_dust')

    def __init__(self, file_directory):
        # file_directory: the name of the RAW file to be processed
        # Instance Variables (Only for specific photo)
        self.processed = False # flag for whether the image has been processed yet
        self.proxy = False # Flag to keep track of whether or not proxies are being used
        self.FileReadError = False # flag for if the class could not read the RAW file
        self.active_processes = 0 # lets object know how many processes are currently processing the photo
        self.pick_wb = False # flag to pick white balance from a set of pixel coordinates
        self.file_directory = file_directory
        self.colour_desc = None # RAW bayer colour description

        # initializing raw processing parameters
        try: # to read in the parameters from a saved file
            directory = self.file_directory.split('.')[0] + '.npy'
            params_dict = np.load(directory, allow_pickle=True).item()
        except: # file does not exist
            for attr in self.processing_parameters:
                if attr in window.global_settings:
                    setattr(self, attr, window.global_settings[attr]) # Initializes every parameter based on default value
                else:
                    setattr(self, attr, 0) # otherwise set to 0
            self.use_global_settings = True # tells GUI class whether to overwrite current photo settings with global setting
        else: # import successful
            for attr in self.processing_parameters:
                if attr in params_dict:
                    setattr(self, attr, params_dict[attr]) # Initializes every parameter with imported parameters
                elif attr in window.default_settings:
                    setattr(self, attr, window.default_settings[attr]) # if parameter doesn't exist, use default
                else:
                    setattr(self, attr, 0) # otherwise set to 0

            self.use_global_settings = False # tells GUI class whether to overwrite current photo settings with global setting

    def load(self, full_res=False):
        # Loads the RAW file into memory
        try:
            with rawpy.imread(self.file_directory) as raw: # tries to read as raw file
                self.RAW_IMG = raw.postprocess(
                    output_bps = 16, # output 16-bit image
                    use_camera_wb = self.use_camera_wb, # Screws up the colours if not used
                    user_wb = self.wb_mult, # wb multipliers
                    demosaic_algorithm = rawpy.DemosaicAlgorithm(self.dm_alg),
                    output_color = rawpy.ColorSpace(self.colour_space),
                    gamma = self.raw_gamma,
                    auto_bright_thr = 0, # no clipping of highlights
                    exp_preserve_highlights = 1,
                    exp_shift = 2 ** self.exp_shift,
                    half_size = not full_res # take the average of 4 pixels to reduce resolution
                    )
                self.colour_desc = raw.color_desc.decode('utf-8') # get the bayer pattern
        except:
            try:
                self.RAW_IMG = cv2.imread(self.file_directory) # if fails, reads as normal image
                if type(self.RAW_IMG) != np.ndarray:
                    raise Exception
            except: # If fails again, set error attributes
                self.reject = True
                self.FileReadError = True
                return
            else:
                if self.RAW_IMG.dtype == np.uint8:
                    self.RAW_IMG = (self.RAW_IMG).astype(np.uint16, copy=False) * 256 # converts image to 16-bit
        else:
            # RawPy sometimes misreads the RAW image size, this removes any extra black borders
            gray = cv2.cvtColor(cv2.convertScaleAbs(self.RAW_IMG, alpha=(255.0/65535.0)),cv2.COLOR_RGB2GRAY)
            _, thresh = cv2.threshold(gray,0,255,0)
            contours, _ = cv2.findContours(thresh,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            del gray, thresh
            cnt = max(contours, key=cv2.contourArea)
            x,y,w,h = cv2.boundingRect(cnt)
            self.RAW_IMG = self.RAW_IMG[y:y+h,x:x+w,::-1]
        
        self.FileReadError = False
        self.memory_alloc = self.RAW_IMG.nbytes * 4 * 12 # estimation of memory requirements based on the size of the image

    def get_IMG(self, output=None):
        # Returns the converted image at different stages of the process, based on desired output
        if self.FileReadError: # Return nothing when file could not be read
            return
        match output:
            case 'RAW': # return RAW image
                img = cv2.convertScaleAbs(self.RAW_IMG, alpha=(255.0/65535.0))
            case 'Threshold': # return threshold image
                img = self.thresh
            case 'Contours': # generate contour image, then return it
                thresh_img = np.uint8(cv2.cvtColor(self.thresh, cv2.COLOR_GRAY2BGR) / 2)
                thresh_img[:,:,2] = 0 # sets colour of threshold image

                indices = np.indices(thresh_img.shape[:2])
                zebra_width = int(np.max(indices) / 100)
                zebra = np.repeat((np.mod(indices[0] + indices[1], zebra_width * 2) > zebra_width)[:, :, np.newaxis], 3, axis=2)
                thresh_img = np.where(zebra, 0, thresh_img) # applies zebra pattern to threshold image
                img = cv2.addWeighted(cv2.convertScaleAbs(self.RAW_IMG, alpha=(255.0/65535.0)), 1, thresh_img, 0.2, 0) # add threshold image to RAW

                # drawing crop boxes
                if self.rect is not None:
                    def shrink_box(box, x, y):
                        # given box with 4 corner coordinates, returns new box coordinates shrunken by x and y percentages
                        sorted = np.sort(box, 0)
                        h = (sorted[2,1] + sorted[3,1] - sorted[0,1] - sorted[1,1]) / 2
                        w = (sorted[2,0] + sorted[3,0] - sorted[0,0] - sorted[1,0]) / 2
                        centre = np.mean(box, 0)
                        y_offset = int(y / 100 * h)
                        x_offset = int(x / 100 * w)
                        offset = np.zeros_like(box)
                        offset[box[:,1] < centre[1], 1] += y_offset
                        offset[box[:,1] > centre[1], 1] -= y_offset
                        offset[box[:,0] < centre[0], 0] += x_offset
                        offset[box[:,0] > centre[0], 0] -= x_offset
                        new_box = box + offset
                        return new_box.astype(np.int32)
                    border_width = np.ceil((img.shape[0] + img.shape[1]) / 800) # border width proportional to image size
                    if img.shape[0] > img.shape[1]:
                        x_crop = self.border_crop
                        y_crop = self.border_crop * img.shape[1] / img.shape[0]
                    else:
                        y_crop = self.border_crop
                        x_crop = self.border_crop * img.shape[0] / img.shape[1]
                    y, x = img.shape[0], img.shape[1]
                    rect = ((self.rect[0][0]*y, self.rect[0][1]*x), (self.rect[1][0]*y, self.rect[1][1]*x), self.rect[2])
                    box = cv2.boxPoints(rect)
                    box = np.int64(box)
                    extra_crop_box = shrink_box(box, x_crop, y_crop)
                    EQ_ignore_box = shrink_box(extra_crop_box, self.ignore_border[0], self.ignore_border[1])
                    EQ_ignore_poly = np.zeros_like(img)
                    cv2.fillPoly(EQ_ignore_poly, [extra_crop_box], (0,0,255))
                    cv2.fillPoly(EQ_ignore_poly, [EQ_ignore_box], (0,0,0))
                    img = np.where(np.dstack([np.sum(EQ_ignore_poly, (2)) == 0]*3), img, cv2.addWeighted(EQ_ignore_poly, 2, img, 0.8, 0)) # shaded zone where EQ calcs are ignored
                    
                    cv2.drawContours(img,[box],0,(0,255,255), int(border_width * 0.75)) # original crop
                    cv2.drawContours(img, self.largest_contour, -1, (0,255,255), int(border_width * .75)) # largest contour
                    cv2.drawContours(img,[extra_crop_box],0,(0,255,0), int(border_width)) # extra border crop
            case 'Histogram': # returns histogram of preview image
                img = self.draw_histogram(self.IMG)
                img = np.flip(img, 0)
                mask = np.sum(img, 2) == 0
                img[mask] = np.array(self.hist_bg_colour)
            case _: # default case, return preview image
                img = self.IMG
                if self.remove_dust:
                    img = self.fill_dust(img, self.dust_mask)
                img = self.add_frame(img) # add decorative white frame
                img = cv2.convertScaleAbs(img, alpha=(255.0/65535.0))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) # Convert back to RGB
        if output != 'Histogram':
            img = self.rotate(img) # apply rotation to image
        return Image.fromarray(img) # convert image to tkinter-friendly image
        
    def __str__(self):
        # returns file name when str() is called on photo
        return os.path.basename(self.file_directory)
    
    def export(self, filename):
        # Saves final image to disk.
        # filename is a string containing the directory and file name with the file extension
        if not hasattr(self, 'IMG'):
            return
        filetype = filename.split('.')[-1]
        img = self.IMG
        if self.remove_dust:
            img = self.fill_dust(img, self.dust_mask)
        img = self.add_frame(self.rotate(img)) # add decorative white frame
        match filetype:
            case 'JPG':
                quality = [cv2.IMWRITE_JPEG_QUALITY, self.jpg_quality]
                cv2.imwrite(filename, cv2.convertScaleAbs(img, alpha=(255.0/65535.0)), quality) # Must convert to 8-bit image before exporting as JPG
            case 'TIFF':
                quality = [cv2.IMWRITE_TIFF_COMPRESSION, self.tiff_compression]
                cv2.imwrite(filename, img, quality)
            case _:
                cv2.imwrite(filename, img)

    def save_settings(self):
        # saves the processing parameters to a file
        directory = self.file_directory.split('.')[0] + '.npy' # uses the same name as the input file
        params_dict = dict()
        for attr in self.processing_parameters:
            params_dict[attr] = getattr(self, attr)
        np.save(directory, params_dict)
    
    def process(self, full_res=False, recent_only=False, skip_crop=False):
        # Selection of appropriate film processing type
        # full_res uses the full resolution raw image for processing, otherwise use downsampled proxy
        # recent_only will not update final output if multiple, more recent processes are started before it finishes
        # skip_crop: skip calculating crop (faster if crop parameters have not changed)
        if not hasattr(self, 'RAW_IMG'):
            self.load() # tries to load file if it hasn't already been done
        if self.FileReadError:
            return # Do not process if the file could not be read
        self.active_processes += 1 # Used to keep track of the number of processes currently running

        if not skip_crop or not hasattr(self, 'thresh'):
            self.thresh, self.rect, self.largest_contour = self.find_optimal_crop()
            
            img_size = self.RAW_IMG.shape[0] + self.RAW_IMG.shape[1]
            if (img_size > self.max_proxy_size): # Checks if image is larger than the allowable size, if yes, then generate proxy images to speed up preview generation
                # Downscales the image to a smaller size
                scale_factor = self.max_proxy_size / img_size
                x = int(self.RAW_IMG.shape[1] * scale_factor)
                y = int(self.RAW_IMG.shape[0] * scale_factor)
                self.proxy_RAW_IMG = cv2.resize(self.RAW_IMG, (x, y))
                self.proxy = True # Flag to tell the rest of the program that proxies are being used

        # Uses a proxy to generate preview, when needed. During final export, will use full resolution
        if self.proxy and not full_res:
            img = self.proxy_RAW_IMG
        else:
            img = self.RAW_IMG

        img = self.crop(img, self.rect)

        dust_mask = self.find_dust(img)

        # Additional processing specific to each film type
        match self.film_type:
            case 0:
                img = self.bw_negative_processing(img)
            case 1:
                img = self.colour_negative_processing(img)
            case 2:
                img = self.slide_processing(img)
            case 3:
                img = self.crop_only(img)

        self.active_processes -= 1
        if recent_only and (self.active_processes > 0):
            return # skip displaying final image if it is not the last active process

        # Set all the global variables once processing is finished
        self.IMG = img
        self.dust_mask = dust_mask
        self.processed = True

    def bw_negative_processing(self, img):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # converts to b/w
        img = 65535 - img # invert to create positive image
        img = self.hist_EQ(img) # increases contrast to maximize dynamic range
        img = self.exposure(img) # exposure adjustment
        img = img.clip(0, 65535).astype(np.uint16, copy=True)
        return img

    def colour_negative_processing(self, img):
        img = 65535 - img # invert to create positive image
        img = self.slide_processing(img) # The rest of the processing is identical to slide_processing
        return img
    
    def slide_processing(self, img):
        img = self.hist_EQ(img) # Maximizes dynamic range
        wb_mode = [self.wb_adjust, self.wb_adjust_coeff, self.wb_adjust_gamma] # different ways to adjust wb, for debugging
        img = wb_mode[1](img) # modifiers for white balancing
        img = self.exposure(img) # Exposure adjustment
        img = self.sat_adjust(img) # modifier for colour saturation
        img = img.clip(0, 65535).astype(np.uint16, copy=True)
        return img
        
    def crop_only(self, img):
        # No processing required
        return img
    
    def find_dust(self, img):
        # work in progress. Tries to detect dust particles of a maximum size, then returns threshold image of just dust
        y, x, _ = img.shape
        img_size = (x + y) / 2
        multiplier = img_size / 800
        max_dust_size = multiplier ** 2 * self.max_dust_area
        kernel_size = max(round(multiplier) * 2 + 1,1)
        kernel = np.ones((kernel_size,kernel_size),np.uint8)
        x, y = (np.array(self.ignore_border) / 100 * img.shape[:2][::-1]).astype(np.int32) # calculates the width of the border to ignore in pixels
        if x * y == 0:
            sample = np.s_[:]
        else:
            sample = np.s_[y:-y, x:-x]

        img8 = cv2.convertScaleAbs(img, alpha=(255.0/65535.0))
        imgray = cv2.cvtColor(img8, cv2.COLOR_BGR2GRAY) # converts to b&w
        minimum = np.percentile(imgray[sample], 0.5)
        maximum = np.percentile(imgray[sample], 99.5)
        threshold = (maximum - minimum) * self.dust_threshold / 100 + minimum
        _, thresh = cv2.threshold(imgray, threshold, 255, cv2.THRESH_BINARY_INV)
        thresh_img = cv2.dilate(thresh,kernel,iterations = self.dust_iter)
        thresh_img = cv2.erode(thresh_img,kernel,iterations = self.dust_iter)
        contours, _ = cv2.findContours(thresh_img, 1, 2)
        contours = sorted(contours, key=lambda x: cv2.contourArea(x))
        smallest = [contour for contour in contours if cv2.contourArea(contour) < max_dust_size]
        dust_mask = np.zeros_like(imgray)
        dust_mask = cv2.drawContours(dust_mask, smallest, -1, 255, cv2.FILLED)
        dust_mask = cv2.dilate(dust_mask, kernel, iterations=1)
        return dust_mask
    
    def fill_dust(self, img, dust_mask):
        # work in progress, uses dust threshold image to erase dust
        if len(img.shape) == 3:
            channels = cv2.split(img)
            filled = []
            for channel in channels:
                filled.append(cv2.inpaint(channel, dust_mask, 3, cv2.INPAINT_TELEA))
            filled = cv2.merge(filled)
        else:
            filled = cv2.inpaint(img, dust_mask, 3, cv2.INPAINT_TELEA)
        return filled

    def find_optimal_crop(self):
        # Determines the optimal crop around an image and corrects for misalignment/rotation
        thresh = self.get_threshold(self.RAW_IMG)
        #thresh = self.get_edges(img) # experimental threholding using edge detection
        contours, _ = cv2.findContours(thresh, 1, 2)
        if len(contours) == 0:
            return thresh, None, None # if no contours are found, skip cropping
        largest_contour = max(contours, key=cv2.contourArea)
        rect = cv2.minAreaRect(largest_contour) # bounding box of largest contour
        y, x = self.RAW_IMG.shape[0], self.RAW_IMG.shape[1]
        rect = ((rect[0][0]/y, rect[0][1]/x), (rect[1][0]/y, rect[1][1]/x), rect[2]) # normalizes crop for different sized images
        return thresh, rect, largest_contour
    
    def crop(self, img, rect):
        if rect != None:
            y, x = img.shape[0], img.shape[1]
            rect = ((rect[0][0]*y, rect[0][1]*x), (rect[1][0]*y, rect[1][1]*x), rect[2]) # convert normalized crop to corresponding pixel coordinates
            box = cv2.boxPoints(rect)
            box = np.int64(box)
            width = int(rect[1][0])
            height = int(rect[1][1])
            src_pts = box.astype('float32')
            dst_pts = np.array([[0, height-1],
                            [0, 0],
                            [width-1, 0],
                            [width-1, height-1]], dtype='float32')
            M = cv2.getPerspectiveTransform(src_pts, dst_pts)
            img = cv2.warpPerspective(img, M, (width, height))
            if rect[2] > 45:
                img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE) # rotates image back if it has been rotated
        if (self.border_crop != 0) & (np.min(img.shape[0:2]) > 100):
            min_dim = np.min(img.shape[0:2])
            crop_px = int(self.border_crop / 100 * min_dim)
            if crop_px != 0:
                img = img[crop_px:-crop_px,crop_px:-crop_px] # applying extra crop to remove borders
        return img
    
    def get_edges(self, img):
        # experimental, attempt at smarter image thresholding, not used
        img = cv2.convertScaleAbs(img, alpha=(255.0/65535.0))
        imgray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # converts to b&w
        blurred = cv2.GaussianBlur(imgray, (5,5), 0)
        max_val = 0
        min_val = abs(self.threshold) / 100 * 255
        edges = cv2.Canny(blurred, min_val, max_val)
        kernel = np.ones((5,5),np.uint8)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 20, None, 50, 10)
        output = np.zeros_like(edges)
        if lines is not None:
            for i in range(0, len(lines)):
                l = lines[i][0]
                cv2.line(output, (l[0], l[1]), (l[2], l[3]), 255, 2, cv2.LINE_AA)
        
        output = cv2.dilate(output,kernel,iterations = 8)
        output = cv2.erode(output,kernel,iterations = 8)
        if self.threshold > 0:
            output = 255 - output
        return output

    def get_threshold(self, img):
        # Generates the threshold image used to find contours
        img = cv2.convertScaleAbs(img, alpha=(255.0/65535.0))
        imgray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # converts to b&w
        dark_threshold = int(self.dark_threshold / 100 * 255)
        _, dark_thresh_img = cv2.threshold(imgray, dark_threshold, 255, 0)
        light_threshold = int(self.light_threshold / 100 * 255)
        _, light_thresh_img = cv2.threshold(imgray, light_threshold, 255, cv2.THRESH_BINARY_INV)
        thresh_img = cv2.bitwise_and(dark_thresh_img, light_thresh_img)
        kernel = np.ones((7,7),np.uint8)
        thresh_img = cv2.erode(thresh_img, kernel, iterations = 2)
        return thresh_img
    
    def hist_EQ(self, img):
        # Equalizes histogram for each color channel
        sensitivity = 0.2 # multiplier to adjust degree at which the sliders affect the output image
        x, y = (np.array(self.ignore_border) / 100 * img.shape[:2][::-1]).astype(np.int32) # calculates the width of the border to ignore in pixels
        if x * y == 0:
            sample = np.s_[:]
        else:
            sample = np.s_[y:-y, x:-x]

        if self.base_detect and (self.film_type == 1 or self.film_type == 2):
            if self.film_type == 1:
                black_point = 65535 - np.array(self.base_rgb, np.uint16)[::-1] * 256
            else:
                black_point = np.array(self.base_rgb, np.uint16)[::-1] * 256
        else:
            black_point = np.percentile(img[sample], self.black_point_percentile, (0,1))
        black_offsets = self.black_point / 100 * sensitivity * 65535 - black_point
        img = img.astype(np.float32, copy=False)
        img[:,:] = img[:,:] + black_offsets # Sets the black point

        max_array = np.ones_like(black_offsets)
        white_point = np.percentile(img[sample], self.white_point_percentile, (0,1))
        white_multipliers = np.divide(65535 + self.white_point / 100 * sensitivity * 65535, white_point, out=max_array, where=white_point>0) # division, but ignore divide by zero or negative
        img = np.multiply(img, white_multipliers) # Scales the white percentile to 65535
        return img
    
    # \/ Three different white balance functions experimented with \/
    def wb_adjust(self, img):
        # Applies white balance adjustment factors as scalars added to RGB, not used
        # both highlights' and shadows' white balance affected
        multiplier = 200
        if self.pick_wb: # logic to calculated temp and tint values from the wb picker
            self.pick_wb = False
            x, y, r = self.wb_picker_params # unpacks parameters passed in from white balance picker
            wb_mask = self.rotate(np.zeros_like(img[:,:,0], dtype=np.uint8)) # generate blank mask, rotate to same orientation as preview image
            # applying scale factors based on image size
            x = int(x * wb_mask.shape[1])
            y = int(y * wb_mask.shape[0])
            radius = int(min(wb_mask.shape) * r)

            wb_mask = cv2.circle(wb_mask, (x, y), radius, 255, -1) # generate small circle to average pixels with
            wb_mask = self.rotate(wb_mask, True) # rotate image back to default orientation
            meanBGR = cv2.mean(img, wb_mask) # returns BGR tuple containing average of unmasked pixels
            # calculating temp and tint values required to balance average BGR to gray
            G_offset =  (meanBGR[0] + meanBGR[2]) / 2 - meanBGR[1]
            RB_offset = meanBGR[0] - (meanBGR[0] + meanBGR[2]) / 2
            self.temp = max(min(RB_offset / multiplier, 100), -100)
            self.tint = max(min(G_offset / multiplier, 100), -100)
        adjustment = np.array([-self.temp * multiplier, -self.tint * multiplier, self.temp * multiplier], np.float32)
        img = np.add(img, adjustment)
        return img
    
    def wb_adjust_coeff(self, img):
        # Applies white balance adjustment factors as coefficients multiplied into RGB
        # only highlights white balance affected
        multiplier = 200
        if self.pick_wb: # logic to calculated temp and tint values from the wb picker
            self.pick_wb = False
            x, y, r = self.wb_picker_params # unpacks parameters passed in from white balance picker
            wb_mask = self.rotate(np.zeros_like(img[:,:,0], dtype=np.uint8)) # generate blank mask, rotate to same orientation as preview image
            # applying scale factors based on image size
            x = int(x * wb_mask.shape[1])
            y = int(y * wb_mask.shape[0])
            radius = int(min(wb_mask.shape) * r)

            wb_mask = cv2.circle(wb_mask, (x, y), radius, 255, -1) # generate small circle to average pixels with
            wb_mask = self.rotate(wb_mask, True) # rotate image back to default orientation
            B, G, R, _ = cv2.mean(img, wb_mask) # returns BGR tuple containing average of unmasked pixels
            # calculating temp and tint values required to balance average BGR to gray
            self.tint = max(min((G/B+G/R-2)/((B*(G+R)+R*G)/(B*R)) * multiplier, 100), -100)
            self.temp = max(min(((2*G-(2*G+R)*self.tint/multiplier)/2/R-1) * multiplier, 100), -100)
        
        img = np.multiply(img, np.array([1-self.temp/multiplier+self.tint/multiplier/2, 1-self.tint/multiplier, 1+self.temp/multiplier+self.tint/multiplier/2]))
        return img
    
    def wb_adjust_gamma(self, img):
        # Applies white balance adjustment factors using gamma function, not used
        # Highlights and shadows stay the same, only midtones' white balance affected
        img = img / 65535
        if self.pick_wb: # logic to calculated temp and tint values from the wb picker
            self.pick_wb = False
            x, y, r = self.wb_picker_params # unpacks parameters passed in from white balance picker
            wb_mask = self.rotate(np.zeros_like(img[:,:,0], dtype=np.uint8)) # generate blank mask, rotate to same orientation as preview image
            # applying scale factors based on image size
            x = int(x * wb_mask.shape[1])
            y = int(y * wb_mask.shape[0])
            radius = int(min(wb_mask.shape) * r)

            wb_mask = cv2.circle(wb_mask, (x, y), radius, 255, -1) # generate small circle to average pixels with
            wb_mask = self.rotate(wb_mask, True) # rotate image back to default orientation
            meanBGR = cv2.mean(img, wb_mask) # returns BGR tuple containing average of unmasked pixels
            # calculating temp and tint values required to balance average BGR to gray
            target = (meanBGR[0] + meanBGR[2]) / 2
            self.temp = 100 * np.log2(np.log(target) / np.log(meanBGR[0]))
            self.tint = -100 * np.log2(np.log(target) / np.log(meanBGR[1]))
        
        img = np.power(img, (2 ** np.array([self.temp/100, self.tint/100, -self.temp/100])), dtype=np.float32)

        img = img * 65535 # restores orginal range prior to normalization
        return img
    
    def exposure(self, img):
        # Exposure adjustment
        norm = matplotlib.colors.Normalize(0, 65535, True)
        img = norm(img).astype(np.float32, copy=False)
        
        img = (img ** (2 ** (-self.gamma/100))).astype(np.float32, copy=False) # gamma adjustment via gamma correction
        
        # Highlights and shadows formula
        shadows_coefficient = 4.15e-5 * self.shadows ** 2 + 0.02185 * self.shadows
        img += (shadows_coefficient * np.minimum(img - 0.75, 0) ** 2) * img

        highlights_coefficient = -4.15e-5 * self.highlights ** 2 + 0.02185 * self.highlights
        img += (highlights_coefficient * np.maximum(img - 0.25, 0) ** 2) * (1 - img)

        img = np.ma.getdata(img, False) # converts masked array back to normal array
        
        img = img * 65535 # restores orginal range prior to normalization

        return img
    
    def sat_adjust(self, img):
        # Applies saturation adjustment factors
        if self.sat == 100:
            return img # don't run the calculation if no changes are to be made
        sat_adjust = self.sat / 100
        norm = matplotlib.colors.Normalize(0, 65535, True)
        img = norm(np.flip(img, 2)).astype(np.float32, copy=False) # Convert from bgr to rgb, and normalize input to (0,1)
        img = matplotlib.colors.rgb_to_hsv(img) # Convert from rgb to hsv
        img[:,:,1] = np.clip(img[:,:,1] * sat_adjust, 0, 1) # Apply saturation adjustment
        img = matplotlib.colors.hsv_to_rgb(img) # Convert from hsv back to rgb
        img = np.flip(img, 2) * 65535 # Convert from rgb to bgr
        return img
    
    def rotate(self, img, undo=False):
        # Applies flip and rotation to image
        rotation = self.rotation % 4
        if undo: # option for reverse operation
            if self.flip:
                img = np.ascontiguousarray(img[:,::-1])
            match rotation:
                case 0: pass
                case 1: img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                case 2: img = cv2.rotate(img, cv2.ROTATE_180)
                case 3: img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        else:
            match rotation:
                case 0: pass
                case 1: img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                case 2: img = cv2.rotate(img, cv2.ROTATE_180)
                case 3: img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            if self.flip:
                img = np.ascontiguousarray(img[:,::-1])
        return img
    
    def draw_histogram(self, img):
        # Generates histogram plot of image
        hist_plot = np.zeros(self.histogram_plt_size, np.uint8) # Base image for the histogram
        width = self.histogram_plt_size[1]
        height = self.histogram_plt_size[0] - 10 # Leave a little border from the top
        histograms = []
        maxes = []
        if len(img.shape) == 2: # Determines if the image is grayscale
            channels = [img]
            colours = [(255, 255, 255)]
        else:
            channels = cv2.split(img)
            colours = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        bins = [256] # The number of divisions in the histogram
        smoothing = 5
        for channel in channels:
            hist = cv2.calcHist([channel], [0], None, bins, [0, 65536]) # Generates the histogram
            maxes.append(np.max(hist)) # Keeps track of the maximum value of the histogram
            hist[1:-1] = cv2.GaussianBlur(hist[1:-1], (smoothing,smoothing), 0) # Smooths out the histogram
            hist = np.squeeze(hist)
            histograms.append(hist)
        
        for (hist, colour) in zip(histograms, colours):
            if np.max(maxes) != 0:
                hist = hist / np.max(maxes) * height # Scales all histograms to fit in the image
            pts = np.stack((np.linspace(0, width, len(hist)), hist), -1).reshape(-1,1,2).squeeze().tolist() # Reformats hist into a list of 2d points
            pts.insert(0, [0, 0])
            pts.append([width, 0])
            new_plot = np.zeros(self.histogram_plt_size, np.uint8)
            new_plot = cv2.fillPoly(new_plot, np.array([pts]).astype(np.int32), color=colour) # Generates histogram as a polygon
            hist_plot = hist_plot + new_plot # Add current histogram channel to the overall histogram plot
        return hist_plot
    
    def add_frame(self, img):
        # adds decorative white border to the outside of picture
        if self.frame == 0:
            return img
        scale_factor = self.frame / 50 + 1
        new_shape = np.array(img.shape)
        new_shape[0] *= scale_factor
        new_shape[1] *= scale_factor
        new_shape.astype(np.int_)
        frame_img = np.ones(new_shape, np.uint16) * 65535
        x_offset, y_offset = int(img.shape[1] * self.frame / 100), int(img.shape[0] * self.frame / 100)
        frame_img[y_offset:y_offset+img.shape[0], x_offset:x_offset+img.shape[1]] = img
        return frame_img

    def clear_memory(self):
        # Deletes instances of images to save memory
        to_del = ['IMG', 'thresh', 'RAW_IMG', 'proxy_RAW_IMG', 'dust_mask']
        for attr in to_del:
            if hasattr(self, attr):
                delattr(self, attr)
        self.processed = False

    def __sizeof__(self):
        # Returns the size of the largest numpy arrays
        total = 0
        for attr in self.__dict__.keys():
            if type(getattr(self, attr)) == np.ndarray:
                total += getattr(self, attr).nbytes
        return total
    
    def set_wb_from_picker(self, x, y, r=0.01):
        # x, y normalized between 0 and 1 as a proportion along the image height and width
        # r is the radius of a small circle to measure the wb as a proportion of the size of the image
        self.wb_picker_params = (x, y, r)
        self.pick_wb = True # sets flag to measure and set white balance on next processing
        self.process()
    
    def get_base_colour(self, x, y, r=0.01):
        # x, y normalized between 0 and 1 as a proportion along the image height and width
        # r is the radius of a small circle to measure the base colour as a proportion of the size of the image
        base_mask = self.rotate(np.zeros_like(self.RAW_IMG[:,:,0], dtype=np.uint8)) # generate blank mask, rotate to same orientation as preview image
        # applying scale factors based on image size
        x = int(x * base_mask.shape[1])
        y = int(y * base_mask.shape[0])
        radius = int(min(base_mask.shape) * r)

        base_mask = cv2.circle(base_mask, (x, y), radius, 255, -1) # generate small circle to average pixels with
        base_mask = self.rotate(base_mask, True) # rotate image back to default orientation
        raw = cv2.convertScaleAbs(self.RAW_IMG, alpha=(255.0/65535.0))
        meanBGR = cv2.mean(raw, base_mask)[:-1] # returns BGR tuple containing average of unmasked pixels
        self.base_rgb = tuple([round(x) for x in reversed(meanBGR)])

class AutoScrollbar(ttk.Scrollbar):
   # A scrollbar that hides itself if it's not needed.
   # Only works if you use the grid geometry manager!
    def set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            # grid_remove is currently missing from Tkinter!
            self.tk.call('grid', 'remove', self)
        else:
            self.grid()
        ttk.Scrollbar.set(self, lo, hi)
    def pack(self, **kw):
        raise tk.TclError('cannot use pack with this widget')
    def place(self, **kw):
        raise tk.TclError('cannot use place with this widget')

class ScrollFrame:
    def __init__(self, master):
        self.vscrollbar = AutoScrollbar(master)
        self.vscrollbar.grid(row=0, column=1, sticky=tk.N+tk.S)
        self.hscrollbar = AutoScrollbar(master, orient=tk.HORIZONTAL)
        self.hscrollbar.grid(row=1, column=0, sticky=tk.E+tk.W)

        self.canvas = tk.Canvas(master, yscrollcommand=self.vscrollbar.set, xscrollcommand=self.hscrollbar.set, takefocus=0, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky=tk.N+tk.S+tk.E+tk.W)

        self.vscrollbar.config(command=self.canvas.yview)
        self.hscrollbar.config(command=self.canvas.xview)

        # make the canvas expandable
        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1)

        # create frame inside canvas
        self.frame = ttk.Frame(self.canvas)
        self.frame.rowconfigure(1, weight=1)
        self.frame.columnconfigure(1, weight=1)

        self.frame.bind('<Configure>', self.reset_scrollregion)
        self.frame.bind('<Enter>', lambda _: self.frame.bind_all('<MouseWheel>', self._on_mousewheel))
        self.frame.bind('<Leave>', lambda _: self.frame.unbind_all('<MouseWheel>'))

    def update(self):
        self.canvas.create_window(0, 0, anchor=tk.NW, window=self.frame)
        self.frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox('all'))

        if self.frame.winfo_reqwidth() != self.canvas.winfo_width():
            # update the canvas's width to fit the inner frame
            self.canvas.config(width = self.frame.winfo_reqwidth())
        if self.frame.winfo_reqheight() != self.canvas.winfo_height():
            # update the canvas's height to fit the inner frame
            self.canvas.config(height = self.frame.winfo_reqheight())
    
    def reset_scrollregion(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
    
    def _on_mousewheel(self, event):
        # binding mousewheel event to scrolling
        caller = event.widget
        if not (isinstance(caller, ttk.Spinbox) or isinstance(caller, ttk.Combobox)): # ignore scrolling on spinboxes and comboboxes
            if platform.system() == 'Windows': # setting different scrolling speeds based on platform
                delta_scale = 120
            else:
                delta_scale = 1
            if (self.frame.winfo_reqheight() > self.canvas.winfo_height()):
                self.canvas.yview_scroll(int(-1*(event.delta/delta_scale)), 'units')

if __name__ == '__main__':
    # Main function
    multiprocessing.freeze_support()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)

        def resource_path(relative_path):    
            try:       
                base_path = sys._MEIPASS
            except Exception:
                base_path = os.path.abspath('.')

            return os.path.join(base_path, relative_path)

        datafile = 'camera-roll.ico'
        if not hasattr(sys, 'frozen'):
            datafile = os.path.join(os.path.dirname(__file__), datafile)
        else:
            datafile = os.path.join(sys.prefix, datafile)
    except:
        root = tk.Tk()
    else:
        root = tk.Tk()
        root.iconbitmap(default=resource_path(datafile))

    window = GUI(root)
    root.mainloop()