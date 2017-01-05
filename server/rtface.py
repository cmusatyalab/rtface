#! /usr/bin/env python
# in this file, the frames by default are rgb unless state otherwise by the variable name
import concurrent_track
from MyUtils import *
from concurrent_track import AsyncTrackWorker
from vision import *
import Queue
import StringIO
import json
import logging
import multiprocessing
import sys
import os
import threading
import time
from operator import itemgetter
import cv2
import dlib
import numpy as np
from PIL import Image
import traceback
from NetworkProtocol import *
from openfaceClient import OpenFaceClient, AsyncOpenFaceClientProcess
from demo_config import Config
from encryption import encrypt
from framebuffer import FaceFrameBuffer
import copy
from collections import namedtuple

if Config.WRITE_PICTURE_DEBUG:
    remove_dir(Config.WRITE_PICTURE_DEBUG_PATH)
    create_dir(Config.WRITE_PICTURE_DEBUG_PATH)
    track_frame_id=0
DETECT_TRACK_RATIO = 10
FrameTuple=namedtuple('FrameTuple', ['frame','fid'])

class RecognitionRequestUpdate(object):
    def __init__(self, recognition_frame_id, location):
        self.recognition_frame_id = recognition_frame_id
        self.location=location

class FaceTransformation(object):
    def __init__(self, openface_port=9000):
        if Config.DEBUG:
            mpl = multiprocessing.log_to_stderr()
            mpl.setLevel(logging.DEBUG)
        
        if Config.ENCRYPT_DENATURED_REGION:
            if not os.path.isdir(Config.ENCRYPT_DENATURED_REGION_OUTPUT_PATH):
                create_dir(Config.ENCRYPT_DENATURED_REGION_OUTPUT_PATH)
            if os.path.isfile(Config.SECRET_KEY_FILE_PATH):
                secret=open(Config.SECRET_KEY_FILE_PATH).read()
            else:
                secret=encrypt.create_secret(Config.SECRET_KEY_FILE_PATH)
            self.cipher=encrypt.create_cipher(secret)
        
        self.detector = dlib.get_frontal_face_detector()
        self.need_detection=False
        self.faces=[]
        
        self.faces_lock=threading.Lock()
        self.img_queue = multiprocessing.Queue()
        self.trackers_queue = multiprocessing.Queue()
        self.recognition_queue = multiprocessing.Queue()
        
        # openface related
        self.training_cnt = 0
        self.server_ip = u"ws://localhost"
        self.server_port = openface_port
        # changed to two openface_client
        # 1 sync for blocking response
        # another for non-blocking response in detection_process
        self.openface_client = OpenFaceClient(self.server_ip, self.server_port)
        resp = self.openface_client.isTraining()
        LOG.info('resp: {}'.format(resp))
        self.training = json.loads(resp)['val']
        LOG.info('openface is training?{}'.format(self.training))
        
        self.correct_tracking_event = multiprocessing.Event()
        self.correct_tracking_event.clear()
        
        # controlled from proxy.py
        self.tracking_thread_idle_event = threading.Event()
        self.tracking_thread_idle_event.clear()
        self.sync_thread_stop_event=threading.Event()
        self.sync_thread_stop_event.clear()
        self.sync_faces_thread = threading.Thread(target=self.correct_tracking,
                                                  name='bgThread',
                                                  kwargs={'stop_event' : self.sync_thread_stop_event})
        self.sync_faces_thread.start()

        self.detection_process_shared_face_fragments=[]
        self.detection_process_stop_event = multiprocessing.Event()
        self.detection_process_stop_event.clear()
        self.detection_process = multiprocessing.Process(
            target = self.detect,
            name='DetectionProcess',
            args=(self.img_queue,
                  self.trackers_queue,
                  self.recognition_queue,
                  self.server_ip,
                  self.server_port,
                  self.correct_tracking_event,
                  self.detection_process_stop_event,))
        self.detection_process.start()
        self.image_width=Config.MAX_IMAGE_WIDTH

        self.frame_id=0
        self.framebuffer=FaceFrameBuffer(30)

    def remove_failed_trackers(self, faces):
        for face in faces:
            face.tracker.clean()

    def on_recv_detection_update(self, tracker_updates, old_faces):
        valid_prev_faces=[face for face in old_faces if not face.low_confidence]
        detected_faces = tracker_updates['faces']
        LOG.debug('bg-thread received detection # {} faces'.format(len(detected_faces)))
        (tracker_frame, fid) = tracker_updates['frame']
        # current tracking faces
        tracking_faces=[]
        # newly added tracking faces (need backward tracking)
        revalidate_trigger_faces=[]
        for detected_face in detected_faces:
            overlaps=[iou_area(detected_face.roi, old_face.roi) for old_face in valid_prev_faces]
            max_overlaps=0.0
            if len(overlaps) > 0:
                max_overlaps=max(overlaps)
            if max_overlaps > 0.3:
                # matched
                max_overlaps_idx = overlaps.index(max_overlaps)
                old_face = valid_prev_faces.pop(max_overlaps_idx)
                LOG.debug('bg-thread sending calling start_track for existing tracker')
                self.faces_lock.acquire()
                old_face.tracker.start_track(tracker_frame, tuple_to_drectangle(detected_face.roi))
                self.faces_lock.release()
                LOG.debug('bg-thread find match frid {} --> frid {}'.format(old_face.frid, detected_face.frid))
                old_face.frid=detected_face.frid
                tracking_faces.append(old_face)
            else:
                # not matched
                LOG.debug('bg-thread no match new frid {}'.format(detected_face.frid))
                revalidate_trigger_faces.append(detected_face)
                detected_face.name=None
#                tracker = create_tracker(tracker_frame, detected_face.roi, use_dlib=Config.DLIB_TRACKING)
                LOG.debug('bg-thread starting a new tracker process')
                tracker=AsyncTrackWorker()
                tracker.start()
                tracker.start_track(tracker_frame, tuple_to_drectangle(detected_face.roi))
                LOG.debug('bg-thread after tracker starts {}'.format(detected_face.frid))   
                detected_face.tracker = tracker
                tracking_faces.append(detected_face)
        return fid, tracking_faces, revalidate_trigger_faces

            # matched=False
            # for faid, old_face in enumerate(old_faces):
            #     if iou_area(detected_face.roi, old_face.roi) > 0.5:
            #         old_face.tracker.start_track(tracker_frame, tuple_to_drectangle(detected_face.roi))
            #         LOG.debug('bg-thread find match frid {} --> frid {}'.format(old_face.frid, detected_face.frid))
            #         old_face.frid=detected_face.frid
            #         matched=True
            #         new_faces.append(old_face)
            #         break
            # if not matched:
            #     LOG.debug('bg-thread no match new frid {}'.format(detected_face.frid))
            #     detected_face.name=None
            #     tracker = create_tracker(tracker_frame, detected_face.roi, use_dlib=Config.DLIB_TRACKING)
            #     detected_face.tracker = tracker
            #     new_faces.append(detected_face)
        # do not remove the tracker if the confidence is still high
#        new_faces.extend([face for idx, face in enumerate(old_faces) if idx not in matched_old_faces_indices])

            
            # nearest_face = self.find_nearest_face(face, self.faces)
            # if (nearest_face):
            #     face.name = nearest_face.name
            # else:
            #     face.name=None

    def on_recv_recognition_update(self, update, in_fly_recognition_info):
        if (isinstance(update, RecognitionRequestUpdate)):
            in_fly_recognition_info[update.recognition_frame_id] = update.location
        else:
            LOG.debug('received recognition resp {}'.format(update))
            recognition_resp = json.loads(update)
            if (recognition_resp['type'] == FaceRecognitionServerProtocol.TYPE_frame_resp
                and recognition_resp['success']):
                if (len(recognition_resp['name'])==0):
                    LOG.debug('received reg info: unknown')
                    return
                bxid = int(recognition_resp['id'])                
                if (bxid in in_fly_recognition_info):
                    # TODO: add in min distance requirement
                    name=recognition_resp['name']
                    LOG.debug('received reg info: {}'.format(recognition_resp))
                    
                    self.faces_lock.acquire()
                    for face in self.faces:
                        if face.frid == bxid:
                            face.name=name
                    self.faces_lock.release()                             
                    self.framebuffer.update_name(bxid,name)                        
                else:
                    LOG.error('received response but no frame info about the request')
            else:
                LOG.error('received response is not frame_resp or frame_resp success is false')
                
        # nearest_face = self.find_nearest_face(in_fly_recognition_info.pop(frame_id), self.faces)
        # if (nearest_face):
        #     if 'name' in recognition_resp:
        #         nearest_face.name = recognition_resp['name']
        # self.faces_lock.release()
        
    # background thread that updates self.faces once
    # detection process signaled
    def correct_tracking(self, stop_event=None):
        #TODO: should yield computing power unless there are events going on
        # right now in between frames, this loop just keeps computing forever
        in_fly_recognition_info={}
        no_detection=0
        while (not stop_event.is_set()):
            self.tracking_thread_idle_event.wait(1)
            if (not self.tracking_thread_idle_event.is_set()):
                continue
            # update detection
            if (self.correct_tracking_event.is_set()):
                try:
                    tracker_updates = self.trackers_queue.get(timeout=0.1)
                    if tracker_updates['frame'] != None:
                        no_detection=0
                        old_faces=self.faces[::]
                        fid, tracking_faces, new_tracking_faces=self.on_recv_detection_update(tracker_updates,
                                                                                              old_faces)
                        self.faces_lock.acquire()                                        
                        self.faces = tracking_faces
                        self.faces_lock.release()
                        self.remove_failed_trackers([face for face in old_faces if face not in tracking_faces])
                        self.framebuffer.update_bx(fid, new_tracking_faces)
                        LOG.debug('bg-thread updated self.faces # {} faces'.format(len(self.faces)))
                    else:
                        # nothing detected simple way to remove all trackers
                        no_detection+=1
                        if no_detection % 5 == 0:
                            self.faces_lock.acquire()                                        
                            self.faces = []
                            self.faces_lock.release()
                    self.correct_tracking_event.clear()                    
                except Queue.Empty:
                    LOG.debug('bg-thread updating faces queue empty!')                    
                    pass

            # update recognition response
            try:
                update = self.recognition_queue.get(timeout=0.1)
                self.on_recv_recognition_update(update, in_fly_recognition_info)
            except Queue.Empty:
                pass


    def terminate(self):
        self.detection_process_stop_event.set()
        self.sync_thread_stop_event.set()
        self.detection_process.join()
        LOG.info('detection process shutdown!')        
        self.sync_faces_thread.join()
        LOG.info('sync faces thread shutdown!')                
        self.openface_client.terminate()        
        LOG.debug('transformer terminate!')


    def find_nearest_face(self, src, nearby_faces, max_distance=None):
        distances = []
        # find the closest face object
        for face in nearby_faces:
            # doesn't match profile faces
            if face.name == FaceROI.PROFILE_FACE:
                continue
                
            face_center = face.get_location()
            if (isinstance(src, FaceROI)):
                src_center = src.get_location()
            else:
                src_center=src
            distance = euclidean_distance_square(face_center, src_center)
            if max_distance is not None:
                if distance <= max_distance:
                    distances.append(distance)
                else:
                    LOG.info('drift too much. do not update recognition result')         
            else:
                distances.append(distance)                
        if distances:
            (face_idx, _) = min(enumerate(distances), key=itemgetter(1))
            return nearby_faces[face_idx]
        else:
            return None

    # called by recognize listener process in OpenFaceClient.py
    def on_receive_openface_server_result(self, resp, queue=None, recognition_busy_event=None):
        # parse the resp
        resp_json=json.loads(resp)
        if (resp_json['type']== FaceRecognitionServerProtocol.TYPE_frame_resp):
            if (self.training):
                LOG.error('training should use async openface response')
                return

            if (recognition_busy_event.is_set()):
                recognition_busy_event.clear()
                
            LOG.debug('received openface server response: {}'.format(resp[:80]))
            queue.put(resp)

    def send_face_recognition_requests(self, openface_client, frame, rois, frame_id):
        for roi in rois:
            (x1,y1,x2,y2) = roi
            # TODO: really need copy here?
            face_pixels = np.copy(frame[y1:y2+1, x1:x2+1])
            face_string = np_array_to_jpeg_data_url(face_pixels)
            # has to use the same client as mainprocess
            openface_client.addFrameWithID(face_string, 'detect', frame_id)
            frame_id+=1
        return frame_id

    def pic_output_path(self,idx):
        return os.path.normpath(Config.WRITE_PICTURE_DEBUG_PATH+'/'+ str(idx)+'.jpg')

    # detection process functions
    def get_image_from_queue(self, img_queue):
        frame, fid=None, -1
        # get the last element in the queue
        try:
            (frame, fid)=img_queue.get(timeout=1)
        except Queue.Empty:
            pass

        try:
            while True:
                (frame, fid) = img_queue.get_nowait()
        except Queue.Empty:
            pass
        return frame, fid

    def send_recognition_request(self,
                                 rois,
                                 frame,
                                 recognition_busy_event,
                                 recognition_queue,
                                 bxids,
                                 detection_process_openface_client):
        if (not recognition_busy_event.is_set() ):
            recognition_busy_event.set()                                            
            for idx, roi in enumerate(rois):
                (x1,y1,x2,y2) = roi
                face_pixels = frame[y1:y2+1, x1:x2+1]
                face_string = np_array_to_jpeg_data_url(face_pixels)
                roi_center=((x1 + x2)/2, (y1+y2)/2)
                recognition_queue.put(RecognitionRequestUpdate(bxids[idx], roi_center))
                detection_process_openface_client.addFrameWithID(face_string, 'detect', bxids[idx])
                LOG.debug('recognition put in-fly requests on queues')
        else:
            LOG.debug('skipped sending recognition')

    # need thoughts here
    def catchup(self, frame, rois, img_queue, bxids):
        # meanshift tracker for catching up
        LOG.debug('catchup: frame {}'.format(frame))
        LOG.debug('catchup: rois {}'.format(rois))
        trackers = create_trackers(frame, rois)
        LOG.debug('catchup: trackers {}'.format(trackers))
        frame_available = True
        frame_cnt = 0
        while frame_available:
            try:
                frame = img_queue.get_nowait()
                hsv_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
                for tracker in trackers:
                    LOG.debug('catchup: tracker {}'.format(tracker))
                    tracker.update(hsv_frame, is_hsv=True)
                rois=[drectangle_to_tuple(tracker.get_position()) for tracker in trackers]
                frame_cnt +=1
            except Queue.Empty:
                LOG.debug('catched up {} images'.format(frame_cnt))    
                frame_available = False
                faces=[]
            return faces

    def create_faceROIs(self,rois, bxids):
        faces=[]        
        for idx, cur_roi in enumerate(rois):
            face = FaceROI(cur_roi, name=None, frid=bxids[idx])
            faces.append(face)
        return faces
        
    def detect(self,
               img_queue,
               trackers_queue,
               recognition_queue,
               openface_ip,
               openface_port,
               correct_tracking_event,
               stop_event):
        bxid=0
        recognition_busy_event = multiprocessing.Event()
        recognition_busy_event.clear()
        
        try:
            LOG.info('created')
            detector = dlib.get_frontal_face_detector()
            detection_process_openface_client=AsyncOpenFaceClientProcess(
                call_back=self.on_receive_openface_server_result,
                queue=recognition_queue,
                recognition_busy_event=recognition_busy_event,
                server_port=self.server_port
            )
            while (not stop_event.is_set()):
                frame, fid = self.get_image_from_queue(img_queue)
                if frame == None:
                    continue
                rois = detect_faces(frame,
                                    detector,
                                    upsample_num_times=Config.DLIB_DETECTOR_UPSAMPLE_TIMES,
                                    adjust_threshold=Config.DLIB_DETECTOR_ADJUST_THRESHOLD)
                cur_bxids = [bxid+idx for idx, roi in enumerate(rois)]
                faces=[]
                if (len(rois)>0):
                    LOG.debug('fid:{} detected:{}'.format(fid, rois))
                    self.send_recognition_request(rois,
                                                  frame,
                                                  recognition_busy_event,
                                                  recognition_queue,
                                                  cur_bxids,
                                                  detection_process_openface_client
                    )
                    bxid+=len(rois)
                    # catchup is not that useful if we only send selective images to
                    # this detection process
                    # faces=self.catchup(frame, rois, img_queue, cur_bxids)

                    if Config.DOWNSAMPLE_TRACKING != 1:
                        rois = [enlarge_drectangles(roi, Config.DOWNSAMPLE_TRACKING)
                                for roi in rois]
                        frame = downsample(frame, Config.DOWNSAMPLE_TRACKING)

                    faces=self.create_faceROIs(rois, cur_bxids)
                    tracker_updates = {'frame':FrameTuple(frame, fid), 'faces':faces}
                else:
                    tracker_updates = {'frame':None, 'faces':[]}   
                trackers_queue.put(tracker_updates)
                LOG.debug('put detection updates onto the queue # {} faces'.format(len(faces)))
                correct_tracking_event.set()
            # wake thread up for terminating
            correct_tracking_event.set()
        except Exception as e:
            traceback.print_exc()
            raise e
                    
                # profile_face_rois=detect_profile_faces(frame, flip=True)
                # profile_face_start_idx=len(rois)
                # LOG.debug('frontal face roi: {} profile face roi:{}'.format(rois, profile_face_rois))
                # rois.extend(profile_face_rois)
                        
                # if Config.WRITE_PICTURE_DEBUG:
                #     draw_rois(frame,rois, hint="detect")
                #     imwrite_rgb(self.pic_output_path(str(detection_frame_id)+'_detect'), frame)

    def get_tracker_type(self, tracker):
        return type(tracker)

    @timeit
    def track_faces(self, rgb_img, faces):
        LOG.debug('# faces tracking {} '.format(len(faces)))
        if (len(faces) == 0):
            # sleep for 10 ms
            time.sleep(0.005)
        else:
            tracker_type = self.get_tracker_type(faces[0].tracker)
            if tracker_type == meanshiftTracker or tracker_type == camshiftTracker:
                hsv_img = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2HSV)
                for face in faces:
                    face.tracker.update(hsv_img, is_hsv=True)
                    new_roi = face.tracker.get_position()
                    face.roi = drectangle_to_tuple(new_roi)
            elif tracker_type == dlib.correlation_tracker:
                for face in faces:
                    conf=face.tracker.update(rgb_img, face.tracker.get_position())
                    new_roi = face.tracker.get_position()
                    face.roi = drectangle_to_tuple(new_roi)
                    if face.update_tracker_failure(conf):
                        LOG.debug('frontal tracker conf too low {}'.format(conf))
            elif tracker_type == concurrent_track.AsyncTrackWorker:
                LOG.debug('sending imgs to tracker')
                # async update all
                for face in faces:
                    face.tracker.update(rgb_img)
                    LOG.debug('sent img to a worker')
                # get result
                for face in faces:
                    (conf, new_roi) = face.tracker.get_position()
                    # if Config.DOWNSAMPLE_TRACKING != 1:
                    #     new_roi = enlarge_drectangles(new_roi, Config.DOWNSAMPLE_TRACKING)
                    face.roi = drectangle_to_tuple(new_roi)
                    if face.update_tracker_failure(conf):
                        LOG.debug('frontal tracker conf too low {}'.format(conf))
            else:
                raise TypeError("unreconized tracker type: {}".format(tracker_type))

    def add_profile_faces_blur(self, bgr_img, blur_list):
        profile_faces=detect_profile_faces(bgr_img, flip=True)
        for (x1,y1,x2,y2) in profile_faces:
            LOG.debug('detect profile faces: {} {} {} {}'.format(x1,y1,x2,y2))
            profile_face=FaceROI( (int(x1), int(y1), int(x2), int(y2)), name='profile_face')
            try:
                profile_face_json = profile_face.get_json(send_data=False)
                blur_list.append(profile_face_json)
            except ValueError:
                pass

    def get_face_rois(self, face_snippets):
        rois=[]
        for faceROI_json in face_snippets:
            faceROI_dict = json.loads(faceROI_json)
            x1 = faceROI_dict['roi_x1']
            y1 = faceROI_dict['roi_y1']
            x2 = faceROI_dict['roi_x2']
            y2 = faceROI_dict['roi_y2']
            rois.append( (x1,y1,x2,y2) )
        return rois

    encrypt_output_path=lambda self,s: os.path.normpath(os.path.join(Config.ENCRYPT_DENATURED_REGION_OUTPUT_PATH, '{}.jpg'.format(s)))

    get_timestamped_id=lambda self,uid: '{}_{}'.format(time.strftime("%Y-%m-%d-%H-%M-%S"), uid)

    def persist_image(self, rgb_img, face_snippets):
        rois=self.get_face_rois(face_snippets)
        if Config.WRITE_PICTURE_DEBUG:
            for roi in rois:
                draw_rois(rgb_img,rois)
                imwrite_rgb(self.pic_output_path(str(self.frame_id)+'_track'), rgb_img)

        if Config.ENCRYPT_DENATURED_REGION:
            for idx, roi in enumerate(rois):
                denatured_region=get_image_region(rgb_img, roi)
                denatured_region=cv2.cvtColor(denatured_region, cv2.COLOR_RGB2BGR)
                retval, jpeg_data=cv2.imencode('.jpg', denatured_region)
                ciphertext=encrypt.encode_aes(self.cipher, jpeg_data.tobytes())
                uid='{}-{}'.format(self.frame_id, idx)
                output_path=self.encrypt_output_path(self.get_timestamped_id(uid))
                with open(output_path, 'w+') as f:
                    f.write(ciphertext)

    @timeit                
    def swap_face(self,rgb_img, bgr_img=None):
#        im = Image.fromarray(frame)
#        im.save('/home/faceswap-admin/privacy-mediator/image/frame.jpg')
        if Config.DOWNSAMPLE_TRACKING != 1:
            sm_rgb_img = downsample(rgb_img, Config.DOWNSAMPLE_TRACKING)
        else:
            sm_rgb_img = rgb_img
            
        if self.training:
            LOG.debug('main-process stopped openface training!')            
            self.training=False
            self.openface_client.setTraining(False)

#        height, self.image_width, _=rgb_img.shape
#        LOG.debug('received image. {}x{}'.format(self.image_width, height))

        # track existing faces
        self.faces_lock.acquire()
#        faces=self.faces[::]
        self.track_faces(sm_rgb_img, self.faces)
        self.faces_lock.release()

        
        face_snippets = []
        for face in self.faces:
            try:
                face_json = face.get_json(send_data=False)
                face_snippets.append(face_json)
            except ValueError:
                pass

        if self.frame_id % Config.DETECT_FRAME_INTERVAL == 0 or (True in [face.low_confidence for face in self.faces]):
            self.need_detection=True

        if self.need_detection:
            # make sure blurry images is not sent for detection
            if is_clear(rgb_img, threshold=Config.IMAGE_CLEAR_THRESHOLD):
                self.need_detection=False
                self.img_queue.put(FrameTuple(rgb_img,self.frame_id))
            else:
                LOG.debug('image {} too blurry. not running detection'.format(self.frame_id))
            
#        LOG.debug('# faces returned: {}'.format(len(self.faces)))

        self.persist_image(rgb_img, face_snippets)
        output_img = sm_rgb_img
        # need to return this value!
        img=self.framebuffer.push_faceframe(FaceFrame(self.frame_id,
                                                  output_img,
                                                  [copy.copy(face) for face in self.faces]
                                                  ))
        self.frame_id +=1
        return img, face_snippets

    def addPerson(self, name):
        return self.openface_client.addPerson(name)

    # frame is a numpy array
    def train(self, rgb_frame, name):
        # change training to true
        if self.training == False:
            self.training = True
            self.training_cnt = 0
            self.openface_client.setTraining(True)

        # detect the largest face
        rois = detect_faces(rgb_frame, self.detector, largest_only=True, upsample_num_times=1)

        # only the largest face counts
        if (len(rois) > 1):
            LOG.info("more than 1 faces detected in training frame. abandon frame")
            return self.training_cnt, None

        if (len(rois) == 0):
            LOG.debug("No faces detected in training frame. abandon frame")
            return self.training_cnt, None

#        LOG.info("training-adding frame: detected 1 face")

        if 1 == len(rois) :
            (x1,y1,x2,y2) = rois[0]
            face_pixels = np.copy(rgb_frame[y1:y2+1, x1:x2+1]) 

        face = FaceROI(rois[0], data=face_pixels, name="training")            
        face_string = np_array_to_jpeg_data_url(face_pixels)
        
        resp = self.openface_client.addFrame(face_string, name)
        resp = json.loads(resp)
        success = resp['success']
        if success:
            self.training_cnt +=1

        return self.training_cnt, face.get_json()
