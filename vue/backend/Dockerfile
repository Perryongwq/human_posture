
FROM 163.50.34.38:5002/system/python:3.13.5-libgomp

WORKDIR /data-app

COPY requirements.txt .

RUN pip install --index-url http://163.50.34.43:59090 pip --upgrade --trusted-host 163.50.34.43 
RUN pip install --index-url http://163.50.34.43:59090 -r requirements.txt --trusted-host 163.50.34.43 


COPY ./Changelogs.md /data-app/
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--access-log"]