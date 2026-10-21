import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RagStateService } from './services/rag-state.service';
import { HeaderComponent } from './shared/components/header/header.component';
import { DossierDrawerComponent } from './shared/components/dossier-drawer/dossier-drawer.component';
import { BillModalComponent } from './shared/components/bill-modal/bill-modal.component';
import { DesktopLayoutComponent } from './desktop/desktop-layout.component';
import { MobileLayoutComponent } from './mobile/mobile-layout.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    HeaderComponent,
    DossierDrawerComponent,
    BillModalComponent,
    DesktopLayoutComponent,
    MobileLayoutComponent
  ],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App implements OnInit {
  readonly state = inject(RagStateService);

  readonly isMobile = signal<boolean>(
    typeof window !== 'undefined' ? window.innerWidth < 1024 : false
  );

  ngOnInit(): void {
    this.state.init();

    if (typeof window !== 'undefined') {
      const mediaQuery = window.matchMedia('(max-width: 1023px)');
      this.isMobile.set(mediaQuery.matches);
      mediaQuery.addEventListener('change', (e) => {
        this.isMobile.set(e.matches);
      });
    }
  }
}
