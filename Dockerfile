FROM python:3
MAINTAINER Jakub Jastrabik (jastrabik.jakub@icloud.com)
ENV userName=$userName
ENV password=$password
ENV url=$url
WORKDIR /
RUN wget https://github.com/jakubjastrabik/smartzone_exporter/archive/v5.0.zip \
&& unzip v5.0.zip \
&& rm v5.0.zip
RUN pip install -r smartzone_exporter-5.0/requirements.txt
RUN chmod +x smartzone_exporter-5.0/smartzone_exporter.py
EXPOSE 9345
CMD python ./smartzone_exporter-5.0/smartzone_exporter.py -u $userName -p $password -t $url --insecure