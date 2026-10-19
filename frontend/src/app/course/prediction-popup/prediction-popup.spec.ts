import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PredictionPopup } from './prediction-popup';

describe('PredictionPopup', () => {
  let component: PredictionPopup;
  let fixture: ComponentFixture<PredictionPopup>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PredictionPopup]
    })
    .compileComponents();

    fixture = TestBed.createComponent(PredictionPopup);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
