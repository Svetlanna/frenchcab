const courseService = require("../services/courseService.js");


// -------------------------------------
// TEST
// -------------------------------------

async function getTest(req, res) {

    try {

        const data = await courseService.getTests();

        return res.status(200).json({
            success: true,
            data: data
        });

    } catch (error) {

        console.error("Erreur test :", error.message);

        return res.status(500).json({
            success: false,
            message: "Impossible de recuperer le test"
        });
    }
}


// -------------------------------------
// COURSE PAR ID
// -------------------------------------

async function getTrouverCourseParId(req, res) {

    try {

        const { uid_trajet } = req.query;

        console.log("Parametre reçu :", req.query);

        if (!uid_trajet) {

            return res.status(400).json({
                success: false,
                message: "Le parametre uid_trajet est obligatoire"
            });
        }

        const course = await courseService.getTrouverCourseParId(uid_trajet);

        if (!course) {

            return res.status(404).json({
                success: false,
                message: "Course non trouvee"
            });
        }

        return res.status(200).json({
            success: true,
            course: course
        });

    } catch (error) {

        console.error("Erreur recuperation course :", error.message);

        return res.status(500).json({
            success: false,
            message:"Impossible de contacter la base de donnees"
        });
    }
}


// -------------------------------------
// LISTE DES COURSES
// -------------------------------------

async function getCourses(req, res) {

    try {

        const limit = Number(req.query.limit) || 100;

        const offset = Number(req.query.offset) || 0;

        const courses = await courseService.getCourses(limit, offset);

        return res.status(200).json({
            success: true,
            courses: courses,
            limit: limit,
            offset: offset
        });

    } catch (error) {

        console.error("Erreur recuperation courses :", error.message);

        return res.status(500).json({
            success: false,
            message:"Impossible de contacter la base de donnees"
        });
    }
}



module.exports = {getTest, getTrouverCourseParId, getCourses};