# Film Scan Converter
A standalone application used for processing RAW film scans from a digital camera into final images  
![image](https://github.com/user-attachments/assets/ed4f2e61-0fa0-404f-bdea-c34ea1925662)

# Installation
To run Film Scan Converter, you'll need Python 3.10 or newer installed on your system. Follow these steps:

1. [Install Python 3.10 or newer](https://www.python.org/downloads/) if you haven't already.
2. Install [Git](https://git-scm.com/) if you haven't already.
3. Clone the repository:
   ```
   git clone https://github.com/jwrossee/Film-Scan-Converter
   cd Film-Scan-Converter
   ```
4. Create and activate a virtual environment:
   - On macOS and Linux:
     ```
     python3 -m venv venv
     source venv/bin/activate
     ```
   - On Windows:
     ```
     python -m venv venv
     venv\Scripts\activate
     ```
4. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
5. Run the application:
   - On macOS and Linux: Execute `python "Film-Scan-Converter.py"` in your terminal.
   - On Windows: Run `python "Film-Scan-Converter.pyw"` in your command prompt.

Note: Always activate the virtual environment before running the application.

Note: For other operating systems, you may need to adapt the commands slightly, but the general process remains the same.

# Scanning Best Practices
Having consistent, high quality scans will go a long way to maximize the effectiveness of this application. For best results, ensure the following during scanning:
1. Use a film holder to hold the film flat and undistorted during scanning.
2. Use a reasonably accurate mask around the photo. Some film holders have notches or cutouts around the film frame; masking tape can be used to cover up the notches and square off the edges.  
_Note: It is possible to scan without a mask, however the program may have trouble distinguishing the edge of the photo from the film base, especially if the photo is underexposed._
3. Use a blower brush or equivalent to remove dust from the film before scanning.
4. Fill the image frame as much as possible with the desired photo.  
_Note: It is not critical to precisely align the photo with the image frame; the automatic cropping should take care of this._
5. Use a high CRI light source as a backlight and minimize stray light from external light sources.
6. Expose "to the right" of the histogram, maximizing the exposure, while ensuring that no part of the image is clipped.
7. Use a consistent exposure and orientation across the entire roll of film.
8. Capture one extra blank frame with just the film base visible, using the same exposure as the rest of the roll, with all other sources of bright lights masked out.

An ideal film scan is shown below:  
![image](https://github.com/user-attachments/assets/7aa530f8-f0b6-4345-bfed-0cb2fa739b9c)

Example film base scan:
![image](https://github.com/user-attachments/assets/667d2393-8ebf-469e-9b2d-888913c7b043)

# How to Use It
## Batch Processing
This application enables you to import multiple RAW scans (most RAW image formats supported), and process them all simultaneously. Each photo's settings can either be synced with global settings, or have settings independent from all the other photos. This is useful when all the photos are scanned in a consistent manner, or you want to dial in the same "look" for multiple photos.

A potential workflow is as follows:
1. Import RAW scans from the same batch and film stock. By default, all photos are synced with global settings.
2. Set the film type (i.e. B&W, Colour, Slide).
3. Set the dark and light threshold so that most photos are cropped properly.
4. If the entire roll has been scanned on the reverse side, the image can be flipped.
5. If applicable, set the colour of the film base.
6. Go through each photo to check that it has been cropped/inverted properly. You can use the arrow keys to cycle through each photo.
7. If an individual photo needs adjustment, uncheck "Sync with Global Settings", then apply the adjustment.
8. Set the export settings, then click "Export All Photos".

## Automatic Cropping
By setting the appropriate dark and light threshold values, the application can automatically find the optimal crop around a photo, even if it is off-center or misaligned. The dark and light threshold values define the minimum and maximum brightness levels of the region of the RAW scan to highlight for retention. An appropriately thresholded image highlights most if not the entirety of the desired image, and excludes the mask and/or the film base. In the "Threshold" view, it should look like a white box surrounded by a black border, as shown below:  
![image](https://github.com/user-attachments/assets/4a768370-e47c-48a8-b76f-8cd934c5d924)

You can verify that the application has detected the photo properly using the "Contours" view. The final crop of the photo is shown as a green rectangle, as shown below.  
![image](https://github.com/user-attachments/assets/fd3e44ec-31f6-4054-8ad6-28ee4ad2ae37)

If the mask has fuzzy edges, this may show up near the borders of the final image. You can either increase the Border Crop, or fine tune the light and dark threshold values to try to crop it out.

## Colour Correction
By default, each colour channel will be equalized such that the darkest point is pure black and the lightest point is pure white. This produces pleasing colours under most circumstances; however, there may be instances where this algorithm is thrown off by the scanning method or by the particular photo itself. If the colours look wrong in the preview, check the following:
- Is the photo cropped properly? If the final crop contains parts of the film holder or the backlight, the photo may be colour balanced against objects apart from of the photo itself.
- If shadows are the wrong colour, the film base colour is likely incorrect and will need to be manually set. This can be done by one of three ways:
  1. Pick the film base colour from the RAW scan.
  2. Set the RGB value manually.
  3. Import the blank scan of the film base from the same roll.
- If the white balance is wrong, it can be corrected by manually adjusting the temperature and tint values, or by using the white balance picker and clicking on any neutral gray portion of the image.
- If sprocket holes are desired in the final image, they will need to be masked out for the equalization calculation. This can be done by going to Edit -> Advanced Settings -> EQ Ignore Borders %, and increasing the height parameter until the sprocket holes are masked. For 35mm film, a value of 15% usually works. To visualize this masking, it is displayed in the "Contours" view as a red border within the cropped region, as shown below:  
![image](https://github.com/user-attachments/assets/41ef16e7-def5-4a36-9d6d-d7c685c5b1ab)
