import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DossierPanelComponent } from '../shared/components/dossier-panel/dossier-panel.component';
import { GraphPanelComponent } from '../shared/components/graph-panel/graph-panel.component';

@Component({
  selector: 'app-desktop-layout',
  standalone: true,
  imports: [CommonModule, DossierPanelComponent, GraphPanelComponent],
  templateUrl: './desktop-layout.component.html'
})
export class DesktopLayoutComponent {}
