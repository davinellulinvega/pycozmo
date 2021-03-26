#!/usr/bin/python
# -*- coding: utf-8 -*-
from queue import Queue, Empty
import math
import time
import numpy as np
import cv2 as cv
import pycozmo as pc
from pycozmo.multi_tracking import MultiTracker, ObjCat, TrackType

# Instantiate a multi-tracker for detecting faces only
TRACKER = MultiTracker(TrackType.MOSSE, skip_frames=5,
                       obj_cats=[ObjCat.HEAD, ObjCat.HAND], conf_thres=0.5,
                       conf_decay_rate=0.995, img_w=480, img_h=480)

# This is required since OpenCV can only display frames from the main thread
IMG_QUEUE = Queue()

# Those two constants are used when sharpening the image with the unsharp mask
# algorithm
SHARP_AMOUNT = 0.7
SHARP_GAMMA = 2.2

# Some more constants to store the robots current status
HEAD_TILT = (pc.MAX_HEAD_ANGLE.radians - pc.MIN_HEAD_ANGLE.radians) * 0.1
HEAD_INC = math.radians(4)
HEAD_LIGHT = False

# If you want the camera to only be in grayscale, set this to False
COLOR_CAMERA = True


# Define a function for handling new frames received by the camera
def on_camera_img(cli, image):
    """
    Detect and track any head that appear in the frame using yolov4-tiny.
    :param cli:
    :param image:
    :return: None
    """
    global IMG_QUEUE, TRACKER, SHARP_AMOUNT, SHARP_GAMMA

    # Convert the image to a numpy array
    frame = np.array(image)

    # Check if the frame is in color
    if frame.shape[-1] == 3:
        # OpenCV mainly works with BGR formatted images so we need to convert
        # the frame
        frame = cv.cvtColor(frame, cv.COLOR_RGB2BGR)

    # Rescale the image
    scaled_frame = cv.resize(frame, None, fx=2, fy=2,
                             interpolation=cv.INTER_LANCZOS4)

    # Try to sharpen the image as much as we can
    blurred_frame = cv.GaussianBlur(scaled_frame, (3, 3), 0)
    sharp_frame = cv.addWeighted(scaled_frame, 1 + SHARP_AMOUNT,
                                 blurred_frame, -SHARP_AMOUNT,
                                 gamma=SHARP_GAMMA)

    # Let the tracker detect the different faces
    # (this is where the heavy lifting happens)
    TRACKER.step(sharp_frame)

    # The draw the bounding boxes on the frame
    TRACKER.draw_bounding_boxes(sharp_frame)

    # Finally send the result back to the main thread
    IMG_QUEUE.put(sharp_frame)


if __name__ == "__main__":
    # Connect to the robot
    with pc.connect() as cli:
        try:
            # Look forward
            cli.set_head_angle(HEAD_TILT)

            # Enable the camera
            cli.enable_camera(enable=True, color=COLOR_CAMERA)

            # Wait a little bit for the image to stabilize
            time.sleep(2)

            # Handle new incoming images
            cli.add_handler(pc.event.EvtNewRawCameraImage, on_camera_img)

            # Loop forever
            while True:
                try:
                    # Get the next frame with the bounding boxes
                    # A timeout is applied so that the robot might still be
                    # controlled even if no image can be displayed
                    img = IMG_QUEUE.get(timeout=0.5)
                    # Display the image in a dedicated window
                    cv.imshow('Camera', img)
                    IMG_QUEUE.task_done()
                except Empty:
                    pc.logger.warning('Did not get any image from the camera so'
                                      ' not displaying any.')

                # Read the next key event received by OpenCV's main window
                key = cv.waitKey(1)

                # Act accordingly
                if key == ord('q'):
                    # Exit the program
                    break

                elif key in [ord('k'), ord('j')]:
                    if key == ord('k'):
                        # Increase head tilt
                        HEAD_TILT = min(pc.MAX_HEAD_ANGLE.radians,
                                        HEAD_TILT + HEAD_INC)
                    elif key == ord('j'):
                        # Decrease head tilt
                        HEAD_TILT = max(pc.MIN_HEAD_ANGLE.radians,
                                        HEAD_TILT - HEAD_INC)
                    # Set the head angle
                    cli.set_head_angle(HEAD_TILT)

                elif key == ord('l'):
                    # Toggle the head light
                    HEAD_LIGHT = not HEAD_LIGHT
                    # Set the head light
                    cli.set_head_light(enable=HEAD_LIGHT)

                # Display the robot's status
                print("Head angle: {:.2f} degrees, "
                      "Head light enabled: {}".format(math.degrees(HEAD_TILT),
                                                      HEAD_LIGHT), end='\r')

        finally:
            # Set the head down
            cli.set_head_angle(pc.MIN_HEAD_ANGLE.radians)

            # Close all displays opened by OpenCV
            cv.destroyAllWindows()

            # Empty the image queue
            while not IMG_QUEUE.empty():
                IMG_QUEUE.get()
                IMG_QUEUE.task_done()
            IMG_QUEUE.join()
