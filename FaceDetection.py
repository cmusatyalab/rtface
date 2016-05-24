#! /usr/bin/env python
import numpy as np
import cv2
face_cascade = cv2.CascadeClassifier('/home/faceswap-admin/dependency/dependency/opencv-src/opencv-3.1.0/data/lbpcascades/lbpcascade_profileface.xml')


def is_gray_scale(img):
    if len(img.shape) == 2:
        return True
    else:
        return False

# flip is used to set whether an image should be flipped
# in addition to detect profile faces in original images
# lbp cascade detector xml are trained only to detect
# face rotated to one direction. Need to flip
# images to detect faces rotated to another direction
# return value (x1, y1, x2, y2)
def detect_profile_faces(img, flip):
    if not is_gray_scale(img):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    h, w = img.shape
    min_face_size=10
    max_face_size=min(w,h)    
    faces = face_cascade.detectMultiScale(img, minSize=(min_face_size,min_face_size), maxSize=(max_face_size, max_face_size))
    faces=list(faces)

    if flip:
        # flip horizontally
        flipped=cv2.flip(img, 1)
        flipped_faces = face_cascade.detectMultiScale(flipped, minSize=(min_face_size,min_face_size),
                                                      maxSize=(max_face_size, max_face_size))

        for (x,y,fw,fh) in flipped_faces:
            faces.append( (w-x-fw, y, fw,fh) )

    results=[]
    for (x,y,fw,fh) in faces:
        results.append( (x,y, x+fw-1, y+fh-1) )
    # usage: for (x,y,w,h) in faces:
    return results

if __name__ == '__main__':
    img = cv2.imread('test/profile-face4.jpg')

    faces=detect_profile_faces(img, True)
    for (x,y,w,h) in faces:
        cv2.rectangle(img,(x,y),(x+w,y+h),(255,0,0),2)
    cv2.imwrite('output.jpg', img)    
    
    # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # flipped=cv2.flip(gray, 1)

    # h, w = gray.shape
    # print 'w {}, h {}'.format(w,h)
    # max_size=min(w,h)
    # faces = face_cascade.detectMultiScale(gray, minSize=(10,10), maxSize=(max_size,max_size))
    # print faces
    # for (x,y,w,h) in faces:
    #     cv2.rectangle(img,(x,y),(x+w,y+h),(255,0,0),2)
    #     roi_gray = gray[y:y+h, x:x+w]
    #     roi_color = img[y:y+h, x:x+w]

    # cv2.imwrite('output.jpg', img)
    
    # print 'flipped'
    # faces = face_cascade.detectMultiScale(flipped, minSize=(10,10), maxSize=(max_size,max_size))
    # print faces
    # for (x,y,w,h) in faces:
    #     cv2.rectangle(flipped,(x,y),(x+w,y+h),(255,0,0),2)
    #     roi_gray = flipped[y:y+h, x:x+w]
    #     roi_color = flipped[y:y+h, x:x+w]
    # cv2.imwrite('flipped.jpg', flipped)    



    
