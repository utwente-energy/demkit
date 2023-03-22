git clone git@github.com:utwente-energy/demkit.git demkit
mkdir workspace
cd workspace
git clone git@github.com:utwente-energy/demkit-example.git example
cd example
git checkout master
cd ..
cd ..
cd demkit
git checkout master
docker network create demkit_network
cd services
cd docker
robocopy grafana_demo grafana /E
cd ..
docker-compose up -d
cd ..
docker build -f docker/WithoutComponents -t demkit .
copy "docker\docker-compose.yaml" docker-compose.yaml
copy "docker\rundemkit.bat" rundemkit.bat
docker-compose up
echo Done installing DEMKit
pause