IoT Soil Moisture and Power Station Simulation
==============================================

Overview
--------

This project is a Flask-based web application that simulates an IoT-based soil moisture monitoring and power management system. It generates virtual soil sensors within a given geographical area, monitors their moisture levels, identifies dry sensors, optimizes the irrigation route for efficient energy usage, and calculates the required number and capacity of power stations to support the sensors.

The application also provides visualizations through interactive maps built with Folium, allowing users to view:

1.  All sensor locations and moisture levels.
    
2.  The optimized route connecting dry sensors.
    
3.  The placement of power stations based on total power requirements.
    

The project is deployed and accessible at: [**https://smdr-gray.vercel.app**](https://smdr-gray.vercel.app/)

Features
--------

*   Randomized generation of soil moisture sensors within a defined area.
    
*   Automatic identification of dry sensors based on a moisture threshold.
    
*   Route optimization using Nearest Neighbor and 2-Opt algorithms to minimize travel distance.
    
*   Automatic calculation of power requirements per sensor and per power station.
    
*   Placement of power stations based on total power demand and coverage radius.
    
*   Interactive Folium maps displaying sensors, routes, and station locations.
    
*   Simulation summary panel showing key metrics such as power, area, distance, and station count.
    

Tech Stack
----------

**Frontend**

*   HTML
    
*   CSS (via Bootstrap 5)
    

**Backend**

*   Python (Flask Framework)
    

**Libraries and Tools**

*   Folium (for map visualization)
    
*   Paho MQTT (for simulated IoT data publishing)
    
*   Math and Random (for simulation logic)
    
*   Threading (for background MQTT process)
    
*   Vercel (for deployment)

Usage
-----

### Web Application

Visit the deployed version: [**https://smdr-gray.vercel.app**](https://smdr-gray.vercel.app/)

1.  Enter the following input parameters:
    
    *   Center Latitude and Longitude (e.g., coordinates of the farm)
        
    *   Radius (in kilometers)
        
    *   Number of Sensors (options: 16, 36, 40, 44, 50)
        
    *   Tile Area (in mm²)
        
    *   Power per Sensor (in mV)
        
2.  Click **Run Simulation**.
    
3.  The application will display:
    
    *   All Sensors Map
        
    *   Route Optimized View
        
    *   Power Station View
        
4.  The right panel will show computed statistics, including total area, total and optimized power, and the number of required power stations.
    

Local Setup
-----------

To run the project locally, follow these steps:

### Prerequisites

*   Python 3.9 or later
    
*   pip (Python package manager)
    
*   Git
    

### Steps

1.  ```git clone https://github.com/Coderakhilan/Soil-Moisture-Drone-Routing```
    
2.  ```python -m venv venv```

3.  ```source venv/bin/activate``` (for macOS)

4.  ```source venv\Scripts\activate``` (for Windows)
    
6.  ```pip install -r requirements.txt```
    
7.  ```python app.py```
    
8.  To access the application, Open your web browser and go to ```http://127.0.0.1:5000.```
    

How It Works
------------

1.  **Sensor Simulation:** The application generates a specified number of sensors randomly within a circular region defined by the input latitude, longitude, and radius.
    
2.  **Moisture Threshold:** Sensors with moisture levels below 30% are marked as dry and selected for route optimization.
    
3.  **Route Optimization:** The irrigation route connecting all dry sensors is optimized using the Nearest Neighbor algorithm followed by the 2-Opt improvement algorithm.
    
4.  ```Total Power = Power per Sensor × Number of Sensors```

5.  Optimized power is calculated based on the ratio of optimized route distance to the initial route distance.
    
6.  ```Station Power = Power per Sensor × 10```

7.  ```Stations Needed = ceil(Total Power / Station Power)```
    
8.  **Visualization:** Three maps are rendered using Folium to display all sensors, optimized routes, and the distribution of power stations.
    

Deployment
----------

The project is deployed on **Vercel**, which supports Python backend applications via serverless functions. To deploy your own version:

1.  Push your project to GitHub.
    
2.  Link the repository in your Vercel account.
    
3.  Set app.py as the entry point in the configuration.
    
4.  Deploy directly using the Vercel dashboard.
    

License
-------

This project is for academic and demonstration purposes.You are free to modify and use it for educational projects or research demonstrations.