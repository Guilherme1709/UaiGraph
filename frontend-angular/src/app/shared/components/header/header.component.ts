import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RagStateService } from '../../../services/rag-state.service';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './header.component.html'
})
export class HeaderComponent {
  readonly state = inject(RagStateService);
}
