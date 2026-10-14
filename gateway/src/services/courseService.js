const axios = require("axios");

const PYTHON_SERVICE_URL = process.env.BACKEND_URL || "http://backend:3001";


async function getTests() {

    console.log("URL Backend :", PYTHON_SERVICE_URL);

    try {

        const response = await axios.get(`${PYTHON_SERVICE_URL}/test`);
 
        return response.data;

    } catch (error) {

        console.log(error.message);

        throw new Error("Impossible de contacter l'API");    
    }
}


// -------------------------------------
// COURSE PAR ID (via le backend, seul à accéder à la BDD)
// -------------------------------------

async function getTrouverCourseParId(uid_trajet) {
    try {
        const response = await axios.get(`${PYTHON_SERVICE_URL}/courseID`, { params: { uid_trajet } });
        return response.data;
    } catch (error) {
        if (error.response?.status === 404) return null;
        throw error;
    }
}


// -------------------------------------
// LISTE DES COURSES (via le backend)
// -------------------------------------

async function getCourses(limit, offset) {
    const response = await axios.get(`${PYTHON_SERVICE_URL}/courses`, { params: { limit, offset } });
    return response.data;
}


module.exports = {getTests, getTrouverCourseParId, getCourses};
