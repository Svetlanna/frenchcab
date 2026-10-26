const express = require("express");
require("dotenv").config();
const cors = require('cors');
const { createProxyMiddleware } = require("http-proxy-middleware");

const app = express();

app.use(cors());

app.use(express.json());

const courseRoute = require("./src/routes/courseRoute");
const predictionRoute = require("./src/routes/predictionRoute");

// Config de la route + proxy vers mlflow Ui
const MLFLOW_TARGET = "http://conteneur-mlflow:5000";

const mlflowProxy = createProxyMiddleware({
  target: MLFLOW_TARGET,
  changeOrigin: true,
  ws: true,
  pathRewrite: {
    "^/mlflow": "",
  },
  onProxyReq: (proxyReq, req, res) => {
    // Injection de headers éventuels ... authentification ou security token
    proxyReq.setHeader("Host","0.0.0.0");
    proxyReq.setHeader("X-Real-IP","40.89.158.227");
  },
  onError: (err, req, res) => {
    console.error("Erreur Proxxy Mlflow:", err);
    res.status(500).send("La gateway n'a pas pu joindre le serveur MLFlow");
  }
});

app.use("/mlflow", mlflowProxy);

app.use("/course", courseRoute)
app.use("/prediction", predictionRoute)


app.listen(3000, () => {
  console.log(`Application à l'écoute sur le port 3000!`);
});

//testr