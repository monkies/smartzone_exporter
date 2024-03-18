FROM python:3
ENV userName=$userName
ENV password=$password
ENV url=$url
WORKDIR /
COPY smartzone_exporter.py /
COPY requirements.txt /
RUN pip install -r /requirements.txt
RUN chmod +x /smartzone_exporter.py
EXPOSE 9345
CMD python /smartzone_exporter.py -u $userName -p $password -t $url --insecure