# Palm detection on OAK-D

## The model 
You can find the model 'palm_detector.blob' under the 'models' directory, but below are the steps I used to get the file.

The model used is the palm detection model from Mediapipe.
The tflite original model has been converted in tensorflow (.pb) by [PINTO](https://github.com/PINTO0309/PINTO_model_zoo). We need to convert the pb file in Openvino format (.xml and .bin), then in MyriadX format (.blob)

### 1. Get the .pb file from PINTO model zoo


Download this file and execute it : https://raw.githubusercontent.com/PINTO0309/PINTO_model_zoo/main/033_Hand_Detection_and_Tracking/10_new_128x128/download_saved_model_128x128.sh
Many format of the same model are downloaded including an Openvino version, but we don't want this model because we need to include the normalization of the image in the model.
The only file that we are intereted in is : palm_detection.pb

### 2. Convert palm_detection.pb into MyriadX blob
The [Luxonis online converter](http://69.164.214.171:8083/) can do the 2-steps conversion (.pb -> Openvino -> .blob):
- On the first page, 
    - Choose Openvino Version : 2020.1
    - Choose model source: Tensorflow
    - Click Continue
- On the 2nd page:
    - Select the model file "palm_detection.pb"
    - Click on Advanced options
    - Model Optimizer params, use: ```--data_type=FP16 --mean_values [127.5,127.5,127.5] --scale_values [127.5,127.5,127.5] --reverse_input_channels```
    - No need to touch to MyriadX Compile params.
    - Click "Convert". The blob file is generated and downloaded.

Note : at the time of writing, the downloaded file was uncorrectly suffixed by '.bin' instead of '.blob'. In this case, just renamed the file into palm_detector.blob.

**Explanation about the Model Optimizer params :**
- The preview of the OAK-D color camera outputs BGR [0, 255] frames . The original model is expecting RGB [-1, 1] frames. ```--reverse_input_channels``` converts BGR to RGB. ```--mean_values [127.5,127.5,127.5] --scale_values [127.5,127.5,127.5]``` normalizes the frames between [-1, 1].

## Run

Prerequisites: the gen2_develop branch of depthai is installed.

```python3 palm.py```

