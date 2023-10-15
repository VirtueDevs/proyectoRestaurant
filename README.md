# proyectoRestaurant
Un proyecto utilizando microservicios en dónde se maneja los pedidos de un restaurante y gestionando la compra de ingredientes.

Para poder visualizar el funcionamiento del aplicativo, unicamente hay que descargar el repositorio, correr en el terminal, dentro de la carpeta raiz:

docker-compose build

y cuando se complete los procesos, correr:

docker-compose up

Luego hay que ir a la carpeta raiz del proyecto y allí se escribe:  python app.py

Por ultimo, se activa el volumen en docker desktop y se ingresa a la dirección   http://localhost:5000/almacen

Y Ahí se puede observar el funcionamiento, tanto en la web como en la consola con diferentes peticiones.
