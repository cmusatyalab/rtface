#!/usr/bin/env python

import cv2

def enlarge_roi(roi, padding, frame_width, frame_height):
    (x1, y1, x2, y2) = roi
    x1=max(x1-padding,0)
    y1=max(y1-padding,0)
    x2=min(x2+padding,frame_width-1)
    y2=min(y2+padding,frame_height-1)
    return (x1, y1, x2, y2)

# check if rect1 and rect2 intersect
def intersect_rect(rect1, rect2):
    (r1_x1, r1_y1, r1_x2, r1_y2) = rect1
    (r2_x1, r2_y1, r2_x2, r2_y2) = rect2
    return not(r2_x1 > r1_x2
               or r2_x2 < r1_x1
               or r2_y1 > r1_y2
               or r2_y2 < r1_y1)

# check if a roi intersect with any of white list rois    
def overlap_whitelist_roi(whitelist_rois, roi):
    for whitelist_roi in whitelist_rois:
        # if intersect
        if intersect_rect(whitelist_roi, roi):
            return True
    return False
    

# the lower the number is, the higher of blurness    
def variance_of_laplacian(bgr_img):
    # compute the Laplacian of the image and then return the focus
    # measure, which is simply the variance of the Laplacian
    if len(bgr_img.shape) == 3:
        grey_img=cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    else:
        grey_img=bgr_img
    return cv2.Laplacian(grey_img, cv2.CV_64F).var()
    
# detect if an image is blurry
def is_clear(bgr_img, threshold=40):
    if variance_of_laplacian(bgr_img) < threshold:
        return False
    return True
    
