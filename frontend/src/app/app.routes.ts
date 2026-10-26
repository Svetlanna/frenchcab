import { Routes } from '@angular/router';
import { Course } from './course/course';
import { Layout } from './layout/layout';
import { Accueil } from './pages/accueil/accueil';
import { PlanifierTrajet } from './pages/planifier-trajet/planifier-trajet';

// export const routes: Routes = [

//     {
//     path: '',
//     component: Course
//   },

// ];


export const routes: Routes = [
  {
    path: '',
    component: Layout,
    children: [
      { path: '', component: Accueil },
      { path: 'course', component: Course },
      { path: 'planifier', component: PlanifierTrajet },
    ],
  },
  { path: '**', redirectTo: '' },
];



