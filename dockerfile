FROM python:3.12.0

WORKDIR /proyectoRestaurant

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY . .

CMD ["flask", "run"]