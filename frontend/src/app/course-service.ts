import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CoursesResponse } from './course/course.model';
import { environment } from '../environments/environment';

@Injectable({ providedIn: 'root' })
export class CourseService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiBaseUrl}/course/courses`;
  

  getCourses(page: number, limit: number): Observable<CoursesResponse> {
    console.log(environment.apiBaseUrl, this.apiUrl)
    const params = new HttpParams()
      .set('limit', limit)
      .set('offset', (page - 1) * limit);

    return this.http.get<CoursesResponse>(this.apiUrl, { params });
  }
}
