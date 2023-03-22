#!/bin/sh
git clone git@github.com:utwente-energy/demkit.git demkit
mkdir workspace
cd workspace
git clone git@github.com:utwente-energy/demkit-example.git example
cd example
git checkout master
touch demohouse_composed.py
touch demostreeet_composed.py
cd ..
cd ..
cd demkit
git checkout master
sudo docker network create demkit_network
cd services
cd docker
sudo cp -R grafana_demo grafana
sudo chown $USER: -R grafana
cd ..
docker-compose up -d
cd ..
docker build -f docker/WithoutComponents -t demkit .
cp docker/docker-compose.yaml docker-compose.yaml
docker-compose up
