from flask import Flask, request, jsonify
from kafka import KafkaProducer, KafkaConsumer
from pymongo import MongoClient
import threading
import time
import json
import uuid
import os
import logging
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# === Ayarlar ===

# KAFKA_TOPIC = 'devops-topic'
# KAFKA_SERVER = 'localhost:9092'
# KAFKA_BOOTSTRAP_SERVERS = [KAFKA_SERVER]
# MONGO_HOST = 'localhost'
# MONGO_PORT = 27017
# MONGO_USERNAME = 'mongouser'
# MONGO_PASSWORD = 'mongopass'
# MONGO_DB_NAME = 'devops-db'
# MONGO_COLLECTION = 'devops-values'
# MONGO_URI = 'mongodb://'+ MONGO_USERNAME +':'+ MONGO_PASSWORD + '@'+ MONGO_HOST +':'+ str(MONGO_PORT) +'/'

KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'devops-topic')
KAFKA_SERVER = os.getenv('KAFKA_SERVER', 'localhost:9092')
KAFKA_BOOTSTRAP_SERVERS = [KAFKA_SERVER]
MONGO_HOST = os.getenv('MONGO_HOST', 'localhost')
MONGO_PORT = os.getenv('MONGO_PORT', '27017')
MONGO_USERNAME = os.getenv('MONGO_USERNAME', 'mongouser')
MONGO_PASSWORD = os.getenv('MONGO_PASSWORD', 'mongopass')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'devops-db')
MONGO_COLLECTION = os.getenv('MONGO_COLLECTION', 'devops-values')
MONGO_URI = 'mongodb://'+ MONGO_USERNAME +':'+ MONGO_PASSWORD + '@'+ MONGO_HOST +':'+ MONGO_PORT +'/?authSource=admin'

# === Metrics ===
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')

# === Logging adjustments ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# logging.getLogger("kafka").setLevel(logging.WARNING)
# logging.getLogger("urllib3").setLevel(logging.WARNING)
# logging.getLogger("kafka.conn").setLevel(logging.ERROR)

# === Kafka Producer ===
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

admin_client = KafkaAdminClient(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    client_id='devops-topic-creator'
)

topic = NewTopic(
    name=KAFKA_TOPIC,
    num_partitions=1,
    replication_factor=1
)

try:
    admin_client.create_topics([topic])
    logging.info(f"Topic '{KAFKA_TOPIC}' created successfully.")
except TopicAlreadyExistsError:
    logging.error(f"Topic '{KAFKA_TOPIC}' already exists.")
finally:
    admin_client.close()

# === MongoDB Client ===
mongo_client = MongoClient(MONGO_URI)
mongo_collection = mongo_client[MONGO_DB_NAME][MONGO_COLLECTION]

# === 10 saniye sonra mesajı al ve yaz ===
def delayed_consume_and_store(msg_id):

    logging.info("10 seconds started...")

    time.sleep(10)

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id=f'devops-consumer-group-{uuid.uuid4()}',  # Unique group ID
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )

    for message in consumer:
        logging.info(f"message: {message}")
        value = message.value
        if value.get("id") == msg_id:
            logging.info(f"Matching Message found and read from Kafka: {value}")
            mongo_collection.insert_one({
                "value": value.get("value"),
                "timestamp": time.time()
            })
            break

    consumer.close()

# === Metrics Endpoint ===
@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

# === API Endpoint ===
@app.route('/devops-api', methods=['GET', 'POST'])
@REQUEST_LATENCY.time()
def receive_value():
    REQUEST_COUNT.labels(method=request.method, endpoint='/devops-api').inc()
    
    if request.method == 'GET':
        value = request.args.get('value')
    else:
        if request.is_json:
            value = request.get_json().get('value')
        else:
            value = request.form.get('value')

    if not value:
        return jsonify({'error': 'No value provided...!!!'}), 400

    # Benzersiz mesaj ID'si oluştur
    msg_id = str(uuid.uuid4())
    kafka_message = {"id": msg_id, "value": value}

    # Mesajı kafkaya gönder
    producer.send(KAFKA_TOPIC, kafka_message)
    producer.flush()
    logging.info(f"Message is sent to Kafka: {kafka_message}")

    # 10 saniye sonra sadece bu id'li mesajı Kafka'dan oku ve Mongo'ya yaz
    threading.Thread(target=delayed_consume_and_store, args=(msg_id,)).start()

    return jsonify({'message': 'Value get and will be processed...', 'value': value}), 200

if __name__ == '__main__':
    app.run(debug=True)


# 1) pip install flask kafka-python pymongo

# 2) kafka ve mongo db belirtilen adreslerde çalışıyor olmalı
#   2A) docker network create kafka-net
#   2B) docker run -d --name zookeeper --network kafka-net -p 2181:2181 -e ZOOKEEPER_CLIENT_PORT=2181 confluentinc/cp-zookeeper:7.6.0
#   2C) docker run -d --name kafka --network kafka-net -p 9092:9092 \
    # -e KAFKA_BROKER_ID=1 \
    # -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 \
    # -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092 \
    # -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
    # confluentinc/cp-kafka:7.6.0
#   2D) docker run -d --name mongo --network kafka-net -p 27017:27017 -e MONGO_INITDB_ROOT_USERNAME=mongouser -e MONGO_INITDB_ROOT_PASSWORD=mongopass mongo:7

#   docker build . -t devops-case
#   docker run   --env-file .env   -p 5000:5000   --network kafka-net devops-case