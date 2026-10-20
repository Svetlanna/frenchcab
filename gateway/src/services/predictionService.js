const axios = require("axios");

const PYTHON_SERVICE_URL = process.env.BACKEND_URL || "http://backend:3001";



// -------------------------------------
// PREDICTION PYTHON
// -------------------------------------



async function getPrediction(zone_depart, zone_arrivee, date_depart, heure_depart) {

    return axios.get(
        `${PYTHON_SERVICE_URL}/prediction`,
        {
            params: {zone_depart, zone_arrivee, date_depart, heure_depart}
        }
    );
}

async function getZones() {
    return axios.get(`${PYTHON_SERVICE_URL}/zones`);
}

async function getModele() {
    return axios.get(`${PYTHON_SERVICE_URL}/modele`);
}

module.exports = {getPrediction, getZones, getModele};