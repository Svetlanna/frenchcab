const express = require("express");
const router = express.Router();
const predictionControllers = require("../controllers/predictionController");


router.get("/", predictionControllers.getPrediction);
router.get("/zones", predictionControllers.getZones);
router.get("/modele", predictionControllers.getModele);


module.exports = router;