const predictionService = require("../services/predictionService.js");



// -------------------------------------
// PREDICTION
// -------------------------------------

async function getPrediction(req, res) {

    try {

        const {zone_depart, zone_arrivee, date_depart, heure_depart} = req.query;

        console.log("Paramètres reçus :",req.query);

        if (!zone_depart || !zone_arrivee || !date_depart || !heure_depart) {

            return res.status(400).json({
                success: false,
                message:
                    "Les paramètres zone_depart, "
                    + "zone_arrivee, date_depart "
                    + "et heure_depart sont obligatoires"
            });
        }

        const reponse =
            await predictionService.getPrediction(zone_depart, zone_arrivee, date_depart, heure_depart);

        return res.status(200).json({
            success: true,
            reponse: reponse.data
        });

    } catch (error) {

        console.error("Code reçu :", error.response?.status);
        console.error("Réponse reçue :", error.response?.data);
        console.error("Message :", error.message);

        return res.status(error.response?.status || 500).json({
            success: false,
            message:error.response?.data?.detail || error.message
        });
    }
}


async function getZones(req, res) {
    try {
        const reponse = await predictionService.getZones();
        return res.status(200).json({ success: true, reponse: reponse.data });
    } catch (error) {
        console.error("Erreur zones :", error.message);
        return res.status(error.response?.status || 500).json({
            success: false,
            message: error.response?.data?.detail || error.message
        });
    }
}


async function getModele(req, res) {
    try {
        const reponse = await predictionService.getModele();
        return res.status(200).json({ success: true, reponse: reponse.data });
    } catch (error) {
        console.error("Erreur modele :", error.message);
        return res.status(error.response?.status || 500).json({
            success: false,
            message: error.response?.data?.detail || error.message
        });
    }
}


module.exports = {getPrediction, getZones, getModele};