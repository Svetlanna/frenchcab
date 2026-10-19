const express = require("express");
require("dotenv").config();
const cors = require('cors');

const app = express();

app.use(cors());

app.use(express.json());

const courseRoute = require("./src/routes/courseRoute");
const predictionRoute = require("./src/routes/predictionRoute");

app.use("/course", courseRoute)
app.use("/prediction", predictionRoute)


app.listen(3000, () => {
  console.log(`Application à l'écoute sur le port 3000!`);
});

//testr