const axios = require("axios");
const bdd = require("../../connexion.js");

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
// COURSE PAR ID
// -------------------------------------

function getTrouverCourseParId(uid_trajet) {

    return new Promise((resolve, reject) => {

        bdd.get(
            `SELECT * FROM trajets
             WHERE uid_trajet = ?`,
            [uid_trajet],
            (err, result) => {

                if (err) {
                    return reject(err);
                }

                resolve(result);
            }
        );
    });
}


// -------------------------------------
// LISTE DES COURSES
// -------------------------------------

function getCourses(limit, offset) {

    return new Promise((resolve, reject) => {

        bdd.all(
            `SELECT * FROM trajets
             LIMIT ? OFFSET ?`,
            [limit, offset],
            (err, result) => {

                if (err) {
                    return reject(err);
                }

                resolve(result);
            }
        );
    });
}


module.exports = {getTests, getTrouverCourseParId, getCourses};