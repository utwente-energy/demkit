# DEMKit

DEMKit is short for Decentralized Energy Management toolKit. It is designed with a cyber-physcial systems approach in mind to support both the simulation and real-world demonstration experiments of smart grid technhologies. It contains various algorithms to optimize and coordinate the use of energy flexbility to ensure the energy system can facilitate the energy transition towards a sustainable society. Furthermore, it models the behaviour of devices in individual components, such that simulation code can be replaces easily with API calls for real-world experiments on real hardware. Lastly, load-flow simulations are included to assess the performance of these algorithms within power grids.

DEMKit is originally developed at the University of Twente, Enschede, The Netherlands by the Energy Management Research at the University of Twente group. For more information on our research, please visit: https://www.utwente.nl/en/eemcs/energy/

We believe that we can only transition to a sustainable society through transparency and openness. Hence we decided to make our efforts open source, such that society can fully benefit from and contribute to science. We invite everybody to join us in this cause. 

## Knowledge resources

DEMKit is developed based on over 15 years of experience in the energy management research field. Therefore, knowledge resulting from various research projects and scientific publications is included. A list of publications by the responsible research group can be found here: https://www.utwente.nl/en/eemcs/energy/publications/

Furthermore, the following PhD dissertations form the foundation of DEMKit regarding respectively the core principles, optimization and heating models:

- G. Hoogsteen, "A Cyber-Physical Systems Perspective on Decentralized Energy Management", PhD Thesis, University of Twente, Enschede, the Netherlands. Available: https://research.utwente.nl/en/publications/a-cyber-physical-systems-perspective-on-decentralized-energy-mana

- T. van der Klauw, "Decentralized Energy Management with Profile Steering: Resource Allocation Problems in Energy Management", PhD Thesis, University of Twente, Enschede, the Netherlands. Available: https://research.utwente.nl/en/publications/decentralized-energy-management-with-profile-steering-resource-al

- R.P. van Leeuwen, "Towards 100% renewable energy supply for urban areas and the role of smart control", PhD Thesis, University of Twente, Enschede, the Netherlands. Available: https://research.utwente.nl/en/publications/towards-100-renewable-energy-supply-for-urban-areas-and-the-role-

## How to cite

If you use DEMKit for publications, please cite either:

- G. Hoogsteen, "A Cyber-Physical Systems Perspective on Decentralized Energy Management", PhD Thesis, University of Twente, Enschede, the Netherlands. Available: https://research.utwente.nl/en/publications/a-cyber-physical-systems-perspective-on-decentralized-energy-mana
- G. Hoogsteen, J. L. Hurink, and G. J. M. Smit, "DEMKit: a Decentralized energy management simulation and demonstration toolkit," In 2019 IEEE PES Innovative Smart Grid Technologies Europe, Bucharest, 5 pages, October 2019. https://doi.org/10.1109/ISGTEurope.2019.8905439


## Installation

The software requires Python 3.x (3.11 is tested)(https://www.python.org/) and depends on the Python libraries found in the requirements.txt file. Furthermore, it utilizes InfluxDB 1.x (1.8.10 is tested, 2.x is incompatible!)(https://www.influxdata.com/) to store simulation results and data. Optionally, Grafana is often used for visualization (https://grafana.com/).

DEMKit consists of two parts: 
1. The core DEMKit code with all components (this repository)
2. A workspace with so-called simulation scenarios (models), utilizing the components and code of DEMKit. An example can be obtained here: https://github.com/utwente-energy/demkit-example 

Various methods to install DEMKit are possible, provided that the requirements are met. However, we recommned to use one of the following two approaches. For a more detailed description, refer to the setup guide that can be found in the "doc" folder.

### Docker-based setup

#### Setup
The easiest method is to have a setup utilizing Docker (https://www.docker.com/). Provided Docker and Git are installed on your system and you have copied your public SSH key to your Github account settings (https://github.com/settings/keys):

1. Download the setup file from the setup-folder (*.bat for Windows, *.sh for UNIX-based systems) and place it in the folder where you wish to install DEMKit.
2. Execute the file, which should install all software and build the DEMKit Docker image automatically. In the end, a demonstration simulation is executed.

To verify if your setup is functioning, browse to http://localhost:3000, login using username=admin password=admin and select the Example dashboard. Now you should see the results of your first simulation. 

#### Running
You can run simulations by executing the "rundemkit.bat" file (Windows) or execute "docker compose up" on the command-line in the DEMKit folder. The "docker-compose.yaml" file contains the configuration, which you can modify to run another simulation scenario by modifying::

      - DEMKIT_FOLDER=example
      - DEMKIT_MODEL=demohouse
    
An example scenario can be found in the workspace folder. Note that DEMKIT_MODEL reflects the scenario to be loaded, which is the Python file without the "*.py" extension. To create your own simulation scenario, it may be wise to clone/fork our example into a new folder (don't forget to adjust your configuration) as starting base from https://github.com/utwente-energy/demkit-example .

### Custom setup

#### Installation
Experts can install DEMKit on their own, which generally results in better simulation performance, but requires more steps. Assuming this repository is cloned to your system (depending on your operating system and/or specific setups, you may need to substitute "python" with "python3"):

1. Install the dependencies:
    python -m pip install -r requirements.txt
2. Install Grafana and InfluxDB 1.x if not yet installed. Optionally, you may run Grafana and InfluxDB using Docker, for which you can simply execute:
    docker compose up -d services/docker-compose.yml
3. Copy and rename the "conf/usrconf.py.misc" file to "conf/usrconf.py"
4. Modify the configuration file "conf/usrconf.py" to reflect your system's variables and paths.

Refer to the stup guide found in the "doc" folder for further instructions on how to set-up e.g. Grafana to connnect to the correct database.

#### Running
You can run simulations by executing demkit.py with 2 arguments::
    
    python demkit.py -f FOLDER -m MODEL

Here FOLDER and MODEL represent the location and Python file (without the "*.py" extension) of the simulation scenario to be executed. An example scenario (which can be used as base) may be obtained from https://github.com/utwente-energy/demkit-example .


## License

This software is made available under the Apache version 2.0 license: https://www.apache.org/licenses/LICENSE-2.0

The software depends on external software (e.g. Python, Grafana, InfluxDB and optionally Docker) and libraries. These external packages are likely to contain other software which may be licenced under other licenses. It is the user's responsibility to ensure that the use of external software and libraries complies with any relevant licenses. This also applies to created Docker images by the user through the usage and/or execution of the Dockerfile, Docker-compose files, and setup scripts provided with this software. A list of used Python libraries can be found in the requirements.txt file.

## Contact
In case you need assistance, please contact:

Gerwin Hoogsteen:
- https://people.utwente.nl/g.hoogsteen
- g.hoogsteen [at] utwente [dot] nl
- demgroup-eemcs [at] utwente [dot] nl
