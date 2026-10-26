import { ComponentFixture, TestBed } from '@angular/core/testing';
import { PlanifierTrajet } from './planifier-trajet';

describe('PlanifierTrajet', () => {
  let component: PlanifierTrajet;
  let fixture: ComponentFixture<PlanifierTrajet>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PlanifierTrajet],
    }).compileComponents();

    fixture = TestBed.createComponent(PlanifierTrajet);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
