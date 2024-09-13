import openai
import time
import json
import pandas as pd
import os
import multiprocessing
from pdf2image import convert_from_path
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.core.files.storage import default_storage
import requests
import base64
import easyocr
import prrocr

API_KEY = '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'
openai.api_key = API_KEY
client = openai.OpenAI(api_key=API_KEY)
thread = None
reader = easyocr.Reader(['ko','en'], gpu = True)
ocr = prrocr.ocr(lang="ko")

def index(request):
    if not request.session.get('visited'):
        request.session.flush()  # 세션 초기화
        request.session['visited'] = True  # 'visited' 플래그 설정
    chat_history = request.session.get('chat_history', [])
    return render(request, 'main/index.html', {'chat_history': chat_history})

def reset_chat(request):
    global thread, client
    if request.method == "POST":
        request.session['chat_history'] = []
        if thread != None:
            client.beta.threads.delete(thread.id)
        thread = None
        return JsonResponse({"status": "success"})
    return JsonResponse({"error": "Invalid request"}, status=400)
  
def process_image(image_path):
    global ocr
    #result = reader.readtext(image_path, detail = 0)
    result = ocr(image_path)
    print(image_path, "처리완료")
    return " ".join(result)

def upload_record(request):
    global client, imgur_client, API_KEY
    if request.method == 'POST' and request.FILES.get('pdf'):
        pdf_file = request.FILES['pdf']

        pdf_path = default_storage.save(f'temp/{pdf_file.name}', pdf_file)
        pdf_full_path = os.path.join(settings.MEDIA_ROOT, pdf_path)

        image_paths = []

        try:
            images = convert_from_path(pdf_full_path,dpi=600,thread_count=8)
            result = []
            for i, image in enumerate(images):
                print(i, end = ' ')
                image_path = os.path.join(settings.MEDIA_ROOT, f'temp/page_{i}.png')
                image.save(image_path)
                image_paths.append(image_path)
            print()
            result = list(map(process_image, image_paths))
            record = "\n".join(result)
            print(record)
            request.session['record'] = record
            return JsonResponse({"status": "success", "gpt_response": record})
        except Exception as e:
            print(e)
            return JsonResponse({"error": str(e)}, status=500)
        finally:
            os.remove(pdf_full_path)
            
            # 저장된 이미지 파일 삭제
            for image_path in image_paths:
                if os.path.exists(image_path):
                    os.remove(image_path)

    return JsonResponse({"error": "Invalid request"}, status=400)

def main(request):
    global client, thread
    if request.method == "POST":
        if thread == None:
            thread = client.beta.threads.create()
        record = request.session.get('record', str)
        user_message = request.POST.get('message')
        print(record)

        chat_history = request.session.get('chat_history', [])

        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message + "\njson"
        )

        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id="asst_x8FNHvg9hFyhJqvokuYc69xR"
        )

        while run.status != "completed":
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            print("Run status: "+run.status)
            time.sleep(0.5)
        else:
            print("Run completed!")
        messages_response = client.beta.threads.messages.list(thread_id=thread.id)
        messages = messages_response.data
        message_check = json.loads(messages[0].content[0].text.value)
        gpt_message = ""

        client.beta.threads.messages.delete(
            message_id=messages[0].id,
            thread_id=thread.id,
        )

        client.beta.threads.messages.delete(
            message_id=messages[1].id,
            thread_id=thread.id,
        )

        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="assistant",
            content="학생 생활기록부:\n"+record
        )
        
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message
        )

        if not message_check['help']:
            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id="asst_2ulmFlZnYzadnoP2usV476xT"
            )
            while run.status != "completed":
                run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
                print("Run status: "+run.status)
                time.sleep(1)
            else:
                print("Run completed!")
            messages_response = client.beta.threads.messages.list(thread_id=thread.id)
            messages = messages_response.data
            gpt_message = messages[0].content[0].text.value
            client.beta.threads.messages.delete(
                message_id=messages[2].id,
                thread_id=thread.id,
            )
        else:
            fields = list(message_check['field'].split(", "))
            courses = pd.DataFrame()
            try:
                for f in fields:
                    file_path = os.path.join(settings.MEDIA_ROOT, f+".csv")
                    file = pd.read_csv(file_path)
                    courses = pd.concat([courses, file], ignore_index=True)
            except Exception as e:
                return JsonResponse({"user": user_message, "gpt": str(e)})
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content="강좌 목록: \n"+courses.to_json(orient="records", force_ascii=False)
            )
            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id="asst_4fCAfPMV5w1DFZ0yXkPwiyFi"
            )
            while run.status != "completed":
                run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
                print("Run status: "+run.status)
                time.sleep(1)
            else:
                print("Run completed!")
            messages_response = client.beta.threads.messages.list(thread_id=thread.id)
            messages = messages_response.data
            gpt_message = messages[0].content[0].text.value
            
            client.beta.threads.messages.delete(
                message_id=messages[2].id,
                thread_id=thread.id,
            )
        print(client.beta.threads.messages.list(thread_id=thread.id).data)
        chat_history = request.session.get('chat_history', [])
        chat_history.append({"user": user_message, "gpt": gpt_message})

        request.session['chat_history'] = chat_history

        return JsonResponse({"user": user_message, "gpt": gpt_message})

    return JsonResponse({"error": "Invalid request"}, status=400)
