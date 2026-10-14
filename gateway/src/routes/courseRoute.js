const express = require("express");
const router = express.Router();
const courseController = require("../controllers/courseController");


router.get("/", courseController.getTest);
router.get("/courses", courseController.getCourses);
router.get("/courseID", courseController.getTrouverCourseParId);


module.exports = router;