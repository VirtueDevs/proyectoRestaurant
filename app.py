from flask import Flask, render_template, jsonify, request, flash, redirect, url_for
from pymongo import MongoClient
from flask_socketio import SocketIO
from bson import ObjectId
import pymongo
import random
import requests
import logging
import threading
import queue
import datetime
import threading


logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/")
def index():
    return render_template("index.html")

@socketio.on('message')
def handle_message(msg):
    print('Message: ' + msg)

app.secret_key = 'clave'

#Base de datos
client = MongoClient("mongodb://mongo_db:27017/")
db = client['restaurantDB']

ordenes_pendientes = queue.Queue()


class Almacen:
    def __init__(self, db):
        self.db = db

    def verificar_y_comprar_ingredientes(self, receta):
        for ingrediente_info in receta['ingredients']:
            ingrediente = ingrediente_info['name']
            cantidad_requerida = ingrediente_info['quantity']

            # Verificar si el ingrediente está disponible
            ingrediente_db = self.db.almacen.find_one({"name": ingrediente})
            if ingrediente_db is None:
                # Si el ingrediente no está en la base de datos, intentamos comprar la cantidad requerida
                cantidad_comprar = cantidad_requerida
            elif ingrediente_db["quantity"] < cantidad_requerida:
                # Si no hay suficiente cantidad, intentar comprar más
                cantidad_comprar = cantidad_requerida - ingrediente_db["quantity"]
            else:
                # Si hay suficiente cantidad, no necesitamos comprar más
                cantidad_comprar = 0

            # Si necesitamos comprar ingredientes, hacemos la lógica para ello
            if cantidad_comprar > 0:
                cantidad_comprada = self.comprar_ingrediente(ingrediente, cantidad_comprar)
                # Verificar si se compró suficiente cantidad
                if cantidad_comprada < cantidad_comprar:
                    return False

        # Si el código llega aquí, todos los ingredientes están disponibles o comprados
        for ingrediente_info in receta['ingredients']:
            ingrediente = ingrediente_info['name']
            cantidad_requerida = ingrediente_info['quantity']
            self.db.almacen.update_one(
                {"name": ingrediente},
                {"$inc": {"quantity": -cantidad_requerida}}
            )
        return True

#Funcion para comprar ingredientes
    def comprar_ingrediente(self, nombre_ingrediente, cantidad):

    #Api del profesor
        url = 'https://utadeoapi-6dae6e29b5b0.herokuapp.com/api/v1/software-architecture/market-place'
        cantidad_comprada = 0
        
        try:
            # Intenta hacer una solicitud a la API.
            response = requests.get(url, params={'ingredient': nombre_ingrediente})
            
            if response.status_code == 200:
                # Si la respuesta es exitosa, obtiene la cantidad realmente comprada.
                data = response.json()['data']
                cantidad_comprada = data.get(nombre_ingrediente, 0)
                
                if cantidad_comprada > 0:
                    # Si se compró algo, agrega detalles al historial.
                    compra = {
                        "ingrediente": nombre_ingrediente,
                        "cantidad": cantidad_comprada,
                        "fecha": datetime.datetime.utcnow()
                    }
                    self.db.historial_compras.insert_one(compra)
                    
                    # Actualiza el stock en la base de datos.
                    self.actualizar_stock(nombre_ingrediente, cantidad_comprada)
            else:
                logging.error(f"Error al intentar comprar {nombre_ingrediente}. Respuesta: {response.status_code}")
                
        except requests.RequestException as e:
            logging.error(f"Error de red: {str(e)}")
        except KeyError as e:
            logging.error(f"Error de clave en la respuesta de la API: {str(e)}")
        
        return cantidad_comprada
    
    def actualizar_stock(self, nombre_ingrediente, cantidad_comprada):
        
        # lógica para actualizar el stock en la base de datos.
        self.db.almacen.update_one(
            {"name": nombre_ingrediente},
            {"$inc": {"quantity": cantidad_comprada}}
        )
    
def inicializar_ingredientes():
    # Definición de los ingredientes y sus cantidades iniciales
    ingredientes_iniciales = [
        {"name": "tomato", "quantity": 5},
        {"name": "lettuce", "quantity": 5},
        {"name": "lemon", "quantity": 5},
        {"name": "onion", "quantity": 5},
        {"name": "cheese", "quantity": 5},
        {"name": "chicken", "quantity": 5},
        {"name": "rice", "quantity": 5},
        {"name": "meat", "quantity": 5},
        {"name": "ketchup", "quantity": 5},
        {"name": "potato", "quantity": 5},
        # Añade más ingredientes según se necesite
    ]

    # Comprobación e inicialización en la base de datos
    for ingrediente in ingredientes_iniciales:
        ingrediente_db = db.almacen.find_one({"name": ingrediente["name"]})
        if ingrediente_db:
            # Si el ingrediente ya existe, actualizar su cantidad
            db.almacen.update_one({"name": ingrediente["name"]}, {"$set": {"quantity": 5}})
        else:
            # Si el ingrediente no existe, añadirlo
            db.almacen.insert_one(ingrediente)
    
almacen = Almacen(db)

#Agrega al historial los ingredientes comprados
def agregar_a_historial(orden, tipo, ingredientes_comprados=None):
    logging.info(f"Agregando a historial: Orden - {orden}, Tipo - {tipo}, Ingredientes Comprados - {ingredientes_comprados}")
    historial_entry = {
        "orden": orden,
        "tipo": tipo,  
        "timestamp": datetime.datetime.utcnow()
    }
    if tipo == "compra" and ingredientes_comprados:
        historial_entry["ingredientes_comprados"] = ingredientes_comprados
    db.historial.insert_one(historial_entry)

#Ruta para generar orden
@app.route('/generar_orden', methods=['GET', 'POST'])
def generar_orden():
    if request.method == 'POST':
        MAX_INTENTOS = 3
        for _ in range(MAX_INTENTOS):
            receta_seleccionada = seleccionar_receta_aleatoria()
            if almacen.verificar_y_comprar_ingredientes(receta_seleccionada):
                try:
                    # Verificar si '_id' está en receta_seleccionada y, en caso afirmativo, eliminarlo
                    if '_id' in receta_seleccionada:
                        del receta_seleccionada['_id']

                    # Intentar insertar receta_seleccionada en la colección 'ordenes'
                    insert_result = db.ordenes.insert_one(receta_seleccionada)
                    
                except pymongo.errors.DuplicateKeyError:

                    flash("Error al generar la orden: clave duplicada", "danger")
                    continue  
                

                # Agregar orden al historial
                agregar_a_historial(receta_seleccionada, "pedido")
                flash("Orden generada para " + receta_seleccionada["name"], "success")

                # Y luego, elimina la orden de la base de datos usando el ID, las ordenes duran cierto tiempo para dar mas realismo.
                timer = threading.Timer(300.0, eliminar_orden, args=[insert_result.inserted_id])  # 300.0 segundos = 5 minutos
                timer.start()
                
                return redirect(url_for('almacen_route'))
        flash("No se pudo generar una orden después de varios intentos", "danger")
    return redirect(url_for('almacen_route'))

#Eliminar una orden
def eliminar_orden(order_id):
    db.ordenes.delete_one({"_id": order_id})
    print(f"Orden {order_id} eliminada")

# Ruta Historial de Compras
@app.route('/historial_compras', methods=['GET'])
def historial_compras():
    compras = list(db.historial_compras.find({}))
    return render_template('historial_compras.html', compras=compras)

#Ruta ver Recetas
@app.route('/ver_recetas', methods=['GET'])
def ver_recetas():
    recetas = list(db.recipes.find({}))
    return render_template('recetas.html', recetas=recetas)

#Ruta visualizar ordenes
@app.route('/ver_ordenes', methods=['GET'])
def ver_ordenes():
  ordenes = list(db.ordenes.find())
  simplified_ordenes = [
      {"name": orden["name"], "image": orden.get("image", "")}
      for orden in ordenes
  ]
  return render_template('ordenes.html', ordenes=simplified_ordenes)

#Ruta almacen
@app.route('/almacen', methods=['GET'])
def almacen_route():
    ingredientes = list(db.almacen.find({}))
    return render_template('almacen.html', ingredientes=ingredientes)

#Seleccionar receta random
def seleccionar_receta_aleatoria():
    recetas = list(db.recipes.find({}))
    return random.choice(recetas)

if __name__ == "__main__":
    inicializar_ingredientes()
    app.run(debug=True) 