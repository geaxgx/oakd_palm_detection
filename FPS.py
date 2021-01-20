# -*- coding: utf-8 -*-
"""
Created on Fri Sep 22 15:29:32 2017

@author: geaxx
"""
import time
import cv2


    
class FPS: # To measure the number of frame per second
    def __init__(self):
        self.nbf=0
        self.fps=0
        self.start=0
        
    def update(self):
        if self.nbf%10==0:
            if self.start != 0:
                self.stop=time.perf_counter()
                self.fps=10/(self.stop-self.start)
                self.start=self.stop
            else :
                self.start=time.perf_counter()    
        self.nbf+=1
    
    def get(self):
        return self.fps

    def display(self, win, orig=(10,30), font=cv2.FONT_HERSHEY_PLAIN, size=2, color=(0,255,0), thickness=2):
        cv2.putText(win,f"FPS={self.get():.2f}",orig,font,size,color,thickness)

    
class RecordImage:
    def __init__(self,dir,record_max=0,prefix=""):
        self.max=record_max
        self.nb_recorded=0
        if not os.path.exists(dir):
            os.mkdir(dir)
        if dir[-1]!='/':
            dir=dir+'/'
        self.dir=dir
        self.prefix=prefix
    def record(self,img):
        if self.max==0 or self.nb_recorded<self.max:
            while True:
                name=random.randint(1,9999999)
                file_name=self.dir+self.prefix+str(name)+'.jpg'
                if not os.path.exists(file_name):
                    break
            self.nb_recorded+=1

            suffix="%4d - "%self.nb_recorded
            print(suffix+"Create file "+file_name)
            cv2.imwrite(file_name,img,[cv2.IMWRITE_JPEG_QUALITY,100])
            if self.nb_recorded==self.max:
                print("Nb files in %s : %d"%(self.dir,len(glob.glob("%s/*.jpg"%self.dir))))
            return file_name
        else:
            return None
        


 
class WebcamVideoStream:
    def __init__(self, src=0):
        # initialize the video camera stream and read the first frame
        # from the stream
        self.stream = cv2.VideoCapture(src)
        (self.grabbed, self.frame) = self.stream.read()
 
        # initialize the variable used to indicate if the thread should
        # be stopped
        self.stopped = False 
        
    def start(self):
        # start the thread to read frames from the video stream
        Thread(target=self.update, args=()).start()
        return self
 
    def update(self):
        # keep looping infinitely until the thread is stopped
        while True:
            # if the thread indicator variable is set, stop the thread
            if self.stopped:
                return
 
            # otherwise, read the next frame from the stream
            (self.grabbed, self.frame) = self.stream.read()
 
    def read(self):
        # return the frame most recently read
        return self.grabbed,self.frame
 
    def stop(self):
        # indicate that the thread should be stopped
        self.stopped = True
               
