from edgine.src.config.config_server import ConfigServer
from edgine.src.base import EdgineBase
from edgine.src.starter import EdgineStarter
from typing import Any
import pyaudio
import numpy as np
import random
import string
import time
import platform
import collections
import tflite_runtime.interpreter as tflite
from matplotlib import pyplot as plt
from matplotlib.backend_bases import KeyEvent
import librosa
import math

EDGETPU_SHARED_LIB = {
    'Linux': 'libedgetpu.so.1',
    'Darwin': 'libedgetpu.1.dylib',
    'Windows': 'edgetpu.dll'
}[platform.system()]


class Getter(EdgineBase):

    def __init__(self,
                 config_server: ConfigServer,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="GET",
                            config_server=config_server,
                            **kwargs)

        config_server.create_if_unknown("input_device_name", "MacBook Pro Microphone")
        config_server.create_if_unknown("input_chunks", 1024)
        config_server.create_if_unknown("input_format", pyaudio.paInt16)
        config_server.create_if_unknown("input_sample_rate", 44100)
        config_server.create_if_unknown("input_channels", 1)
        config_server.save_config()

        self._cap = None
        self._stream = None
        self.device_index = None

    def prerun(self) -> None:
        self._cap: pyaudio.PyAudio = pyaudio.PyAudio()
        for i in range(self._cap.get_device_count()):
            if self._cap.get_device_info_by_index(i)["name"] == self.cfg.input_device_name:
                self.log(f"Found device index {i}")
                self.device_index = i

        if self.device_index is None:
            self.error(f"Device with name '{self.cfg.input_device_name}' not found. Using default")
            self.device_index = int(self._cap.get_default_input_device_info()["index"])

        for k, v in self._cap.get_device_info_by_index(self.device_index).items():
            self.info(f"{k: >25} : {v}")

        self._stream: pyaudio.Stream = self._cap.open(format=self.cfg.input_format,
                                                      channels=self.cfg.input_channels,
                                                      rate=self.cfg.input_sample_rate,
                                                      input_device_index=self.device_index,
                                                      input=True,
                                                      frames_per_buffer=self.cfg.input_chunks)

    def blogic(self, data_in: Any = None) -> Any:
        data = self._stream.read(self.cfg.input_chunks, exception_on_overflow=False)
        data = np.frombuffer(data, dtype=np.int16)
        return data

    def postrun(self) -> None:
        self._stream.stop_stream()
        self._stream.close()
        self._cap.terminate()
        self.info("Input device closed")


class Combiner(EdgineBase):

    def __init__(self,
                 config_server: ConfigServer,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="COMB",
                            config_server=config_server,
                            **kwargs)
        config_server.create_if_unknown("total_length", 4096)
        time.sleep(1)
        self.pointer = 0
        self.buffer = np.zeros((self.cfg.total_length, ), dtype=np.int16)
        self.sending = False

    def blogic(self, data_in: Any = None) -> Any:
        maxp = math.floor(int(self.cfg.total_length/self.cfg.input_chunks))

        curr = 1
        while curr < maxp:
            self.buffer[(curr-1)*self.cfg.input_chunks:curr*self.cfg.input_chunks] = self.buffer[(curr) * self.cfg.input_chunks:(curr + 1) * self.cfg.input_chunks]
            curr += 1

        self.buffer[-self.cfg.input_chunks:] = data_in[:]

        return self.buffer

    def postrun(self) -> None:
        self.buffer = None
        del self.buffer
        return


class Normaliser(EdgineBase):

    def __init__(self,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="NORM",
                            **kwargs)

    def blogic(self, data_in: Any = None) -> Any:
        data_out = data_in*(np.iinfo(np.int16).max/np.max(data_in))

        return data_out


class FeatureExtractor(EdgineBase):

    def __init__(self,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="FE",
                            **kwargs)

    def blogic(self, data_in: Any = None) -> Any:
        if data_in is None:
            return None

        # self.info(f"Type : {type(data_in)}, shape: {data_in.shape}")
        data_in = data_in.astype(np.float32)
        features = np.empty((0, 193))
        stft = np.abs(librosa.stft(data_in))
        mfccs = np.mean(librosa.feature.mfcc(y=data_in,
                                             sr=self.cfg.input_sample_rate,
                                             n_mfcc=40).T,
                        axis=0)
        chroma = np.mean(librosa.feature.chroma_stft(S=stft,
                                                     sr=self.cfg.input_sample_rate).T,
                         axis=0)
        mel = np.mean(librosa.feature.melspectrogram(data_in,
                                                     sr=self.cfg.input_sample_rate).T,
                      axis=0)
        contrast = np.mean(librosa.feature.spectral_contrast(S=stft,
                                                             sr=self.cfg.input_sample_rate).T,
                           axis=0)

        harmonics = librosa.effects.harmonic(data_in)

        tonnetz = np.mean(librosa.feature.tonnetz(y=harmonics,
                                                  sr=self.cfg.input_sample_rate).T,
                          axis=0)
        ext_features = np.hstack([mfccs, chroma, mel, contrast, tonnetz])
        features = np.vstack([features, ext_features])

        return features


class Classify(EdgineBase):

    def __init__(self,
                 config_server: ConfigServer,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="CLS",
                            config_server=config_server,
                            **kwargs)
        config_server.create_if_unknown("model_file",
                                        "models/sound_edgetpu.tflite")
        config_server.save_config()

        self._interpreter = None
        self._input_details = None
        self._output_details = None

        self.last_pred = None

    def prerun(self) -> None:
        self._interpreter = tflite.Interpreter(
            model_path=self.cfg.model_file,
            experimental_delegates=[tflite.load_delegate(EDGETPU_SHARED_LIB,
                                                         {})])
        self._interpreter.allocate_tensors()
        self._input_details = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()

    def blogic(self, data_in: Any = None) -> Any:
        # make it float32 data
        input_data = data_in.astype(np.float32)

        # self.log(f"input_data : {input_data.shape}")

        # load data into the tensor
        self._interpreter.set_tensor(self._input_details[0]['index'], input_data)

        # run the inference
        self._interpreter.invoke()

        tflite_model_predictions = self._interpreter.get_tensor(self._output_details[0]['index'])

        tmp = np.argmax(tflite_model_predictions[0])

        print(tflite_model_predictions[0])

        if tmp != self.last_pred:
            self.last_pred = tmp
            return tflite_model_predictions[0]
        else:
            return None


class PrintRandom(EdgineBase):

    def __init__(self,
                 **kwargs):
        EdgineBase.__init__(self,
                            name="RAND",
                            **kwargs)

    def blogic(self, data_in: Any = None) -> Any:
        letters = string.ascii_letters
        out = ''.join(random.choice(letters) for i in range(10))
        self.info(out)
        return None


if __name__ == "__main__":
    starter = EdgineStarter(config_file="coral_sound_classification_config.json")
    starter.reg_service(Getter)
    starter.reg_service(Combiner)
    starter.reg_service(Normaliser)
    starter.reg_service(FeatureExtractor, min_runtime=1)
    starter.reg_service(Classify, min_runtime=1)
    starter.reg_service(PrintRandom, min_runtime=10)
    starter.reg_connection(0, 1)
    starter.reg_connection(1, 2)
    starter.reg_connection(2, 3)
    starter.reg_connection(3, 4)
    q3 = starter.reg_sink(2)
    q4 = starter.reg_sink(4)
    starter.init_services()
    starter.start()

    my_file = open("models/sound_labels", "r")
    content_list = my_file.readlines()
    for i in range(len(content_list)):
        content_list[i] = content_list[i][:-1]

    print(content_list)


    def exit_all(event: KeyEvent):
        if event.key == 'q':
            starter.stop()
            print("All done!")
            exit(code=0)


    bigger_sound_chunk = np.zeros(shape=(8192,), dtype=np.int16)
    pointer = 0

    pred_name = "Nothing"

    while True:
        try:
            bigger_sound_chunk = q3.get_nowait()

        except Exception:
            pass

        try:
            pred = q4.get_nowait()

            pred_name = content_list[np.argmax(pred)]

        except Exception:
            pass

        plt.cla()
        plt.plot(bigger_sound_chunk)
        plt.title(pred_name)
        plt.ylim([np.iinfo(np.int16).min, np.iinfo(np.int16).max])
        plt.connect('key_press_event', exit_all)
        plt.pause(0.001)
