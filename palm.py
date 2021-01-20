
from pathlib import Path
import cv2
import depthai as dai
import numpy as np
from collections import namedtuple
from math import sqrt, ceil
from FPS import FPS

class Anchor:
    def __init__(self, x_center=0, y_center=0, w=0, h=0):
        self.x_center = x_center
        self.y_center = y_center
        self.w = w
        self.h = h

class HandRegion:
    def __init__(self, pd_score, pd_box, pd_kps=0):
        self.pd_score = pd_score # Palm detection score 
        self.pd_box = pd_box # Palm detection box [x, y, w, h] normalized
        self.pd_kps = pd_kps # Palm detection keypoints

    def print(self):
        attrs = vars(self)
        print('\n'.join("%s: %s" % item for item in attrs.items()))


SSDAnchorOptions = namedtuple('SSDAnchorOptions',[
        'num_layers',
        'min_scale',
        'max_scale',
        'input_size_height',
        'input_size_width',
        'anchor_offset_x',
        'anchor_offset_y',
        'strides',
        'aspect_ratios',
        'reduce_boxes_in_lowest_layer',
        'interpolated_scale_aspect_ratio',
        'fixed_anchor_size'])

def calculate_scale(min_scale, max_scale, stride_index, num_strides):
    if num_strides == 1:
        return (min_scale + max_scale) / 2
    else:
        return min_scale + (max_scale - min_scale) * stride_index / (num_strides - 1)

def generate_anchors(options):
    """
    option : SSDAnchorOptions
    # https://github.com/google/mediapipe/blob/master/mediapipe/calculators/tflite/ssd_anchors_calculator.cc
    """
    anchors = []
    layer_id = 0
    n_strides = len(options.strides)
    while layer_id < n_strides:
        anchor_height = []
        anchor_width = []
        aspect_ratios = []
        scales = []
        # For same strides, we merge the anchors in the same order.
        last_same_stride_layer = layer_id
        while last_same_stride_layer < n_strides and \
                options.strides[last_same_stride_layer] == options.strides[layer_id]:
            scale = calculate_scale(options.min_scale, options.max_scale, last_same_stride_layer, n_strides)
            if last_same_stride_layer == 0 and options.reduce_boxes_in_lowest_layer:
                # For first layer, it can be specified to use predefined anchors.
                aspect_ratios += [1.0, 2.0, 0.5]
                scales += [0.1, scale, scale]
            else:
                aspect_ratios += options.aspect_ratios
                scales += [scale] * len(options.aspect_ratios)
                if options.interpolated_scale_aspect_ratio > 0:
                    if last_same_stride_layer == n_strides -1:
                        scale_next = 1.0
                    else:
                        scale_next = calculate_scale(options.min_scale, options.max_scale, last_same_stride_layer+1, n_strides)
                    scales.append(sqrt(scale * scale_next))
                    aspect_ratios.append(options.interpolated_scale_aspect_ratio)
            last_same_stride_layer += 1
        
        for i,r in enumerate(aspect_ratios):
            ratio_sqrts = sqrt(r)
            anchor_height.append(scales[i] / ratio_sqrts)
            anchor_width.append(scales[i] * ratio_sqrts)

        stride = options.strides[layer_id]
        feature_map_height = ceil(options.input_size_height / stride)
        feature_map_width = ceil(options.input_size_width / stride)

        for y in range(feature_map_height):
            for x in range(feature_map_width):
                for anchor_id in range(len(anchor_height)):
                    x_center = (x + options.anchor_offset_x) / feature_map_width
                    y_center = (y + options.anchor_offset_y) / feature_map_height
                    new_anchor = Anchor(x_center=x_center, y_center=y_center)
                    if options.fixed_anchor_size:
                        new_anchor.w = 1.0
                        new_anchor.h = 1.0
                    else:
                        new_anchor.w = anchor_width[anchor_id]
                        new_anchor.h = anchor_height[anchor_id]
                    anchors.append(new_anchor)
        
        layer_id = last_same_stride_layer
    return anchors

# Create anchors
# https://github.com/google/mediapipe/blob/master/mediapipe/modules/palm_detection/palm_detection_cpu.pbtxt

anchor_options = SSDAnchorOptions(num_layers=4, 
                                    min_scale=0.1484375,
                                    max_scale=0.75,
                                    input_size_height=128,
                                    input_size_width=128,
                                    anchor_offset_x=0.5,
                                    anchor_offset_y=0.5,
                                    strides=[8, 16, 16, 16],
                                    aspect_ratios= [1.0],
                                    reduce_boxes_in_lowest_layer=False,
                                    interpolated_scale_aspect_ratio=1.0,
                                    fixed_anchor_size=True)
anchors = generate_anchors(anchor_options)
print(f"{len(anchors)} anchors have been created")


def decode_bboxes(score_thresh, wi, hi, scores, bboxes, anchors):
    """
    wi, hi : NN input shape
    mediapipe/calculators/tflite/tflite_tensors_to_detections_calculator.cc
    # Decodes the detection tensors generated by the model, based on
    # the SSD anchors and the specification in the options, into a vector of
    # detections. Each detection describes a detected object.

    https://github.com/google/mediapipe/blob/master/mediapipe/modules/palm_detection/palm_detection_cpu.pbtxt :
    node {
        calculator: "TensorsToDetectionsCalculator"
        input_stream: "TENSORS:detection_tensors"
        input_side_packet: "ANCHORS:anchors"
        output_stream: "DETECTIONS:unfiltered_detections"
        options: {
            [mediapipe.TensorsToDetectionsCalculatorOptions.ext] {
            num_classes: 1
            num_boxes: 896
            num_coords: 18
            box_coord_offset: 0
            keypoint_coord_offset: 4
            num_keypoints: 7
            num_values_per_keypoint: 2
            sigmoid_score: true
            score_clipping_thresh: 100.0
            reverse_output_order: true

            x_scale: 128.0
            y_scale: 128.0
            h_scale: 128.0
            w_scale: 128.0
            min_score_thresh: 0.5
            }
        }
    }
    """
    sigmoid_scores = 1 / (1 + np.exp(-scores))
    regions = []
    for i,anchor in enumerate(anchors):
        score = sigmoid_scores[i]

        if score > score_thresh:
            # If reverse_output_order is true, sx, sy, w, h = bboxes[i,:4] 
            # Here reverse_output_order is true

            sx, sy, w, h = bboxes[i,:4]
            cx = sx * anchor.w / wi + anchor.x_center 
            cy = sy * anchor.h / hi + anchor.y_center
            w = w * anchor.w / wi
            h = h * anchor.h / hi
            box = [cx - w*0.5, cy - h*0.5, w, h]

            kps = {}
            # 0 : wrist
            # 1 : index finger joint
            # 2 : middle finger joint
            # 3 : ring finger joint
            # 4 : little finger joint
            # 5 : 
            # 6 : thumb joint
            for j, name in enumerate(["0", "1", "2", "3", "4", "5", "6"]):
                # Here reverse_output_order is true
                lx, ly = bboxes[i,4+j*2:6+j*2]
                lx = lx * anchor.w / wi + anchor.x_center 
                ly = ly * anchor.h / hi + anchor.y_center
                kps[name] = [lx, ly]
            regions.append(HandRegion(float(score), box, kps))
    return regions

def non_max_suppression(regions, nms_thresh):

    # cv2.dnn.NMSBoxes(boxes, scores, 0, nms_thresh) needs:
    # boxes = [ [x, y, w, h], ...] with x, y, w, h of type int
    # Currently, x, y, w, h are float between 0 and 1, so we arbitrarily multiply by 1000 and cast to int
    # boxes = [r.box for r in regions]
    boxes = [ [int(x*1000) for x in r.pd_box] for r in regions]        
    scores = [r.pd_score for r in regions]
    indices = cv2.dnn.NMSBoxes(boxes, scores, 0, nms_thresh)
    return [regions[i[0]] for i in indices]


# Start defining a pipeline
pipeline = dai.Pipeline()

# Define a source - color camera
cam_rgb = pipeline.createColorCamera()
cam_rgb.setPreviewSize(128, 128)
cam_rgb.setFps(90.0)
cam_rgb.setInterleaved(False)



# Define a neural network that will make predictions based on the source frames
detection_nn = pipeline.createNeuralNetwork()
detection_nn.setBlobPath(str((Path(__file__).parent / Path('models/palm_detection.blob')).resolve().absolute()))

cam_rgb.preview.link(detection_nn.input)

# Create outputs
xout_rgb = pipeline.createXLinkOut()
xout_rgb.setStreamName("rgb")
cam_rgb.preview.link(xout_rgb.input)

xout_nn = pipeline.createXLinkOut()
xout_nn.setStreamName("nn")
detection_nn.out.link(xout_nn.input)

# Pipeline defined, now the device is assigned and pipeline is started
device = dai.Device(pipeline)
device.startPipeline()

# Output queues will be used to get the rgb frames and nn data from the outputs defined above
q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
q_nn = device.getOutputQueue(name="nn", maxSize=4, blocking=False)

frame = None
bboxes = []

fps = FPS()


# nn data, being the bounding box locations, are in <0..1> range - they need to be normalized with frame width/height
def frame_norm(frame, bbox):
    return (np.array(bbox) * np.array([*frame.shape[:2], *frame.shape[:2]])[::-1]).astype(int)

pd_score_thresh = 0.5
pd_nms_thresh = 0.3

while True:
    fps.update()
    # instead of get (blocking) used tryGet (nonblocking) which will return the available data or None otherwise
    in_rgb = q_rgb.get()
    

    if in_rgb is not None:
        # if the data from the rgb camera is available, transform the 1D data into a HxWxC frame
        shape = (3, in_rgb.getHeight(), in_rgb.getWidth())

        frame = in_rgb.getData().reshape(shape).transpose(1, 2, 0).astype(np.uint8)
        frame = np.ascontiguousarray(frame)
        in_nn = q_nn.get()
        # 2 output layers:
        # - classificators:
        # - regressors : 
        # From: print(in_nn.getAllLayerNames())

        if in_nn is not None:
            scores = np.array(in_nn.getLayerFp16("classificators"))
            bboxes = np.array(in_nn.getLayerFp16("regressors")).reshape((896,18))

            # Decode bboxes
            regions = decode_bboxes(pd_score_thresh, 128, 128, scores, bboxes, anchors)
            # Non maximum suppression
            regions = non_max_suppression(regions, pd_nms_thresh)
            for r in regions:
                box = (np.array(r.pd_box) * 128).astype(int)

                cv2.rectangle(frame, (box[0], box[1]), (box[0]+box[2], box[1]+box[3]), (0,255,0), 1)
            

        if frame is not None:
            cv2.putText(frame, "FPS: {:.2f}".format(fps.get()), (10,10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0,0,255), 1)
            cv2.imshow("rgb", frame)
    
    if cv2.waitKey(1) == ord('q'):
        break

