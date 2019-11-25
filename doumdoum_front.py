# !/usr/bin/env python
# -*- coding: utf-8 -*-

'''
The front-end to DOUM Main server Using GIGA Genie
메인서버에 접근하기 위해 기가지니를 이용하는 프론트엔드
Lee Cheolju
Kim Sangwon
Park Jongkuk
'''

from __future__ import print_function
from __future__ import absolute_import
import grpc
import gigagenieRPC_pb2
import gigagenieRPC_pb2_grpc
import MicrophoneStream as MS
import user_auth as UA
import audioop
import os
from ctypes import *
import gkit
import time
import requests

# Constants (GigaGenie)
GENIE_HOST= 'gate.gigagenie.ai'
GENIE_PORT = 4080
RATE = 16000
CHUNK = 512

# 음성기능을 이용하기 위해 사전에...
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
def py_error_handler(filename, line, function, err, fmt):
    dummy_var = 0
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
asound = cdll.LoadLibrary('libasound.so')
asound.snd_lib_error_set_handler(c_error_handler)


# STT 요청에 쓰이게 된다.
def voiceReqGenerator():
    with MS.MicrophoneStream(RATE, CHUNK) as stream:
        audioGenerator = stream.generator()
        for content in audioGenerator:
            msg = gigagenieRPC_pb2.reqVoice()
            msg.audioContent = content
            yield msg
            rms = audioop.rms(content, 2)


# STT
def getTextFromVoice():
    print('getTextFromVoice: Starting...')
    channel = grpc.secure_channel('{}:{}'.format(GENIE_HOST, GENIE_PORT), UA.getCredentials())
    stub = gigagenieRPC_pb2_grpc.GigagenieStub(channel)
    request = voiceReqGenerator()
    resultText = ''
    for response in stub.getVoice2Text(request):
        if response.resultCd == 200: #partial
            resultText = response.recognizedText
            print('getTextFromVoice: recognizedText=%s' % response.recognizedText)
        elif response.resultCd == 201: #final
            resultText = response.recognizedText
        else : # error
            print('getTextFromVoice: resp code %d' % response.resultCd)
            break
    print('getTextFromVoice: result=%s' % resultText)
    return resultText


# TTS
def writeVoiceFileFromText(inText, inFileName):
    channel = grpc.secure_channel('{}:{}'.format(GENIE_HOST, GENIE_PORT), UA.getCredentials())
    stub = gigagenieRPC_pb2_grpc.GigagenieStub(channel)

    msg = gigagenieRPC_pb2.reqText()
    msg.lang = 0
    msg.mode = 0
    msg.text = inText
    writeFile = open(inFileName, 'wb')
    for response in stub.getText2VoiceStream(msg):
        if response.HasField('resOptions'):
            print('writeVoiceFileFromText: resp code %d' % response.resOptions.resultCd)
        if response.HasField('audioContent'):
            print('writeVoiceFileFromText: Writing Audio content.')
            writeFile.write(response.audioContent)
    writeFile.close()
    return response.resOptions.resultCd

# -----------------------

# Constants (chatbot-side)
led = gkit.get_led()
CHAT_URL = 'http://125.181.9.94:5566/api/chat'

def myChatReqData(qtext):
    return {
        'qtext':qtext,
        'meta':{'nickname':'doumdoum_gigagenie_@_%s' % 'demoboy1'}
    }

def myChatbotService():
    cnt = True #continue the dialog?

    while cnt:
        cnt = False
        MS.play_file('signal_youcansay.wav')
        led.set_state(gkit.LED.BLINK_3)
        print('myChatbotService: Detected. listening...')
        sttText = getTextFromVoice()
    
        led.set_state(gkit.LED.ON)
        if sttText != '':
            r = requests.post(CHAT_URL, json=myChatReqData(sttText))
            if r.ok:
                chatbotAnswerText = r.json()['text']
                cnt = ( r.json()['meta'] == 'cnt' )
            else :
                chatbotAnswerText = '챗봇 서버로부터 정상응답을 받는 데 문제가 생겼습니다. ' + r.text
            filename = 'tts_result.wav'
            writeVoiceFileFromText(chatbotAnswerText, filename)
            MS.play_file(filename)

        led.set_state(gkit.LED.PULSE_QUICK)


def main():
    print('doumdoum via GigaGenie')
    print('2019-11-22')
    
    detector = gkit.KeywordDetector()
    try:
        led.set_state(gkit.LED.PULSE_QUICK)
        detector.start(callback = myChatbotService)
    except KeyboardInterrupt:
        detector.terminate()
        led.set_state(gkit.LED.OFF)
        time.sleep(1)
        led.stop()
        print('[END OF THE SERVICE]')


if __name__ == '__main__':
    main()

