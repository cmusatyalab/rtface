'''
Test tracker package
'''

def test_mmap_worker():
    init_bx = dlib.rectangle(230, 182, 445, 397)
    cap = cv2.VideoCapture(sys.argv[1])
    mf = setup_mmap_file()
    worker = MMapAsyncTracker()
    worker.start()
    first = True
    while (True):
        # Capture frame-by-frame
        ret, frame = cap.read()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if first:
            mf[:] = frame.tostring()
            worker.start_track(None, init_bx)
            first = False
        else:
            s = time.time()
            mf[:] = frame.tostring()
            print('writing to mem mapped file took : {:0.3f}'.format((time.time() - s) * 1000))
            worker.update(None)
            conf, pos = worker.get_position()
            print('tracking time: {:0.3f}'.format((time.time() - s) * 1000))

    worker.clean()
    # When everything done, release the capture
    cap.release()


def test_pipe_worker():
    init_bx = dlib.rectangle(230, 182, 445, 397)
    cap = cv2.VideoCapture(sys.argv[1])
    worker = AsyncTrackWorker()
    worker.start()
    first = True
    mf = setup_mmap_file()
    while (True):
        # Capture frame-by-frame
        ret, frame = cap.read()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if first:
            worker.start_track(frame, init_bx)
            first = False
        else:
            s = time.time()
            worker.update(frame)
            conf, pos = worker.get_position()
            print('tracking time: {:0.3f}'.format((time.time() - s) * 1000))

    worker.clean()
    # When everything done, release the capture
    cap.release()


if __name__ == "__main__":
    sys.path.append('test')
    import multiprocessing
    import logging

    mpl = multiprocessing.log_to_stderr()
    mpl.setLevel(logging.DEBUG)
    test_mmap_worker()
