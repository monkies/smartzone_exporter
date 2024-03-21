FROM python:3.7
ENV userName=$userName
ENV password=$password
ENV url=$url
WORKDIR /app
COPY smartzone_exporter.py .
COPY requirements.txt .
RUN pip3 install -r requirements.txt
RUN chmod +x smartzone_exporter.py
EXPOSE 9345
CMD python3 smartzone_exporter.py -u $userName -p $password -t $url --insecure