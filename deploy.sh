docker build -t spring-music:local --build-arg=JAR_FILE=build/libs/spring-music-1.0.jar .
kubectl create deployment spring-music --image=spring-music:local
kubectl expose deployment spring-music --type=LoadBalancer --port=8080
minikube service spring-music
