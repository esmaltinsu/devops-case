# DevOps Case 

## İçindekiler
- [Proje Hakkında](#proje-hakkında)
- [Uygulama Akışı](#uygulamaakışı)
- [Teknolojiler](#teknolojiler)
- [Ön Gereksinimler](#ön-gereksinimler)
- [Kurulum ve Çalıştırma](#kurulum-ve-çalıştırma)
  - [1. Docker Image Build & Test](#1-docker-image-build--test)
  - [2. Minikube ile Kubernetes Cluster Kurulumu](#2-minikube-ile-kubernetes-cluster-kurulumu)
  - [3. Helm ile Deployment](#3-helm-ile-deployment)
  - [4. ArgoCD ile GitOps Deployment](#4-argocd-ile-gitops-deployment)
  - [5. Monitoring (Prometheus & Grafana)](#5-monitoring-prometheus--grafana)
- [CI/CD Süreci](#cicd-süreci)
- [Beklenen Çıktılar](#beklenen-çıktılar)


# Proje Hakkında 

Bu proje, **Kafka ve MongoDB entegrasyonu ile çalışan bir Flask API uygulaması** dır. 
Uygulama, gelen verileri Kafka'ya gönderir, 10 saniye sonra bu verileri Kafka'dan 
okuyarak MongoDB'ye kaydeder.

 1. ANA UYGULAMA (app.py)
- **Flask API**: `/devops-api` endpoint'i ile GET/POST isteklerini kabul eder
- **Kafka Producer**: Gelen verileri Kafka'ya gönderir
- **Kafka Consumer**: 10 saniye sonra verileri Kafka'dan okur
- **MongoDB**: Okunan verileri MongoDB'ye kaydeder

Teknolojiler : 

- Python (Flask)
- Kafka
- MongoDB
- Docker 
- Kubernetes + Helm
- GitHub Actions (CI/CD)
- GHCR (GitHub Container Registry) 
- Argo CD (GitOps)
- Prometheus & Grafana (Monitoring)

## Ön Gereksinimler

- Docker
- Minikube
- kubectl
- Helm
- GitHub ve GHCR (GitHub Container Registry) erişimi

## Docker Image Build & Test

Local Çalıştırma: 

>> pip install flask kafka-python pymongo

2) kafka ve mongo db belirtilen adreslerde çalışıyor olmalı
```sh
  >> docker network create kafka-net
  >> docker run -d --name zookeeper --network kafka-net -p 2181:2181 -e ZOOKEEPER_CLIENT_PORT=2181 confluentinc/cp-zookeeper:7.6.0
  >> docker run -d --name kafka --network kafka-net -p 9092:9092 \
     -e KAFKA_BROKER_ID=1 \
     -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 \
     -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092 \
     -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
     confluentinc/cp-kafka:7.6.0 '''
  >> docker run -d --name mongo --network kafka-net -p 27017:27017 -e MONGO_INITDB_ROOT_USERNAME=mongouser -e MONGO_INITDB_ROOT_PASSWORD=mongopass mongo:7

   >> git clone https://github.com/esmaltinsu/devops-case.git
   >> cd devops-case
   >> docker build . -t devops-case
   >> docker run   --env-file .env   -p 5000:5000   --network kafka-net devops-case

        GET için: 
            http://localhost:5000/devops-api?value=esma browserdan gidin

        POST için: 
             curl -POST http://localhost:5000/devops-api -H "Content-Type: application/json" -d {"value": "esma-test"}'
                                 veya
             curl "http://localhost:5000/devops-api?value=test"

### 2. Minikube Kurulumu

```sh
minikube start --driver=docker

### GHCR-Secret (ghcr den tag çekebilmemiz için) 

(Github üzerinden Personal access token oluşturulmalı read: packages yetkisi önemli.)

kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=<github-username> \
  --docker-password=<github-personal-access-token> \
  --namespace devops-case
```

---

**** MongoDB'nin Ayrı Servis Olarak Kurulması **** 
(açıklaması readme.md sonunda)

Bitnami chart’ı yerine ARM64 uyumlu resmi MongoDB imajı ile kendi manifestlerin kullanıldı:

```sh
kubectl apply -f mongo-deployment.yaml
kubectl apply -f mongo-service.yaml
```

### 3. Helm ile Deployment

```sh
>> kubectl create namespace devops-case
>> helm upgrade --install devops-case ./chart -n devops-case
>> minikube service devops-case -n devops-case

Servislere Erişim 

>>> minikube service devops-case -n devops-case
# veya
>>> kubectl port-forward svc/devops-case -n devops-case 5000:5000

---

### 4. ArgoCD ile Deployment

```sh
>> kubectl create namespace argocd
>> kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
>> kubectl port-forward svc/argocd-server -n argocd 8080:443
# https://localhost:8080
>> kubectl apply -f argocd/Application.yaml
```
(password için: >> kubectl -n devops-case get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)

### 5. Monitoring (Prometheus & Grafana)

```sh
>> helm install monitoring prometheus-community/kube-prometheus-stack \
    --set prometheus.service.type=NodePort \
    --set prometheus.service.nodePort=31090 \
    --set grafana.service.type=NodePort \
    --set grafana.service.nodePort=31091 \
    --set grafana.adminPassword=admin123
>> kubectl port-forward svc/monitoring-grafana -n default 3000:80
# http://localhost:3000 (admin / admin123)
kubectl port-forward svc/monitoring-kube-prometheus-prometheus -n default 9090:9090
# http://localhost:9090
```

#### Pod Metriklerini Görüntüleme**
Grafana panelinde:
- Pod CPU:
  
  sum(rate(container_cpu_usage_seconds_total{namespace="devops-case"}[5m])) by (pod)
  
- Pod Memory:
  
  sum(container_memory_usage_bytes{namespace="devops-case"}) by (pod)
  

  Metrics Endpoint Testi:
  >> curl "http://localhost:5000/metrics"
  Prometheus uyumlu metrikler dönmelidir.

## CI/CD Süreci

Her maine push’ta GitHub Actions workflow otomatik olarak:
Docker image’ı build eder ve GHCR’a push eder.
Helm values.yaml’daki image tag’ini günceller.
(ArgoCD - Helm ile) otomatik deployment tetiklenir.
ArgoCD UI üzerinden podlar izlenebilir. 
Grafanadan tüm nesnelerin durumu izlenebilir.

## Beklenen Çıktılar

- Tüm pod’lar ve servisler “Running” ve “UP” olmalı.
- ArgoCD UI’da uygulama “Healthy” ve “Synced” görünmeli.
- Prometheus “Targets” ekranında devops-case namespace’inde uygulamanın /metrics endpoint’i “UP” olmalı.
- Grafana’da pod bazlı CPU ve memory metrikleri canlı olarak izlenebilmeli.
- CI/CD pipeline’ı başarılı şekilde image build, push ve deploy işlemlerini yapmalı.


## Ekstra Notlar

- ServiceMonitor ve PodMonitor CRD’ları ile uygulamanın metrikleri Prometheus tarafından otomatik olarak scrape edilir.
- Tüm kaynaklar (deployment, service, configmap, secret, servicemonitor, vs.) Helm chart’ı ile yönetilir.

** **MongoDB Neden Ayrı Servis/Manifest ile Kuruldu?**
  - Bitnami MongoDB Helm chart’ı ARM64 mimarilerde stabil çalışmadığı için, doğrudan resmi MongoDB Docker imajı ve kendi `mongo-deployment.yaml` ile Kubernetes’e deploy edildi.
  - Bu sayede hem ARM64 hem de x86_64 mimarilerde sorunsuz çalıştı.
  - Uygulama ile MongoDB bağlantısı environment variable ve Kubernetes secret/configmap ile yönetildi.

---
