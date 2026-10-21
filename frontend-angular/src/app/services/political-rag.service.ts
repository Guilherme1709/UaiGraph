import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface GraphStats {
  nodes: number;
  relationships: number;
  politicians: number;
  parties: number;
  bills: number;
}

export interface PoliticianProfile {
  name: string;
  photo_url?: string;
  email?: string;
  camara_id?: number;
  uf?: string;
  party?: string;
  bio?: string;
  total_bills?: number;
  total_connections?: number;
  centrality_score?: number;
  sample_bills?: string[];
}

export interface ChatResponse {
  question: string;
  entities: string[];
  answer: string;
  graph: {
    nodes: Array<{
      id: string;
      label: string;
      category: string;
      photo_url?: string;
      party?: string;
      relation?: string;
      camara_id?: number;
      ementa?: string;
    }>;
    edges: Array<{
      from: string;
      to: string;
      label: string;
    }>;
  };
  politician?: PoliticianProfile;
}

@Injectable({
  providedIn: 'root'
})
export class PoliticalRagService {
  private http = inject(HttpClient);
  private baseUrl = environment.apiUrl;

  getStats(): Observable<GraphStats> {
    return this.http.get<GraphStats>(`${this.baseUrl}/api/stats`);
  }

  askQuestion(question: string, depth: number = 1, maxNodes: number = 25): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.baseUrl}/api/chat`, { question, depth, max_nodes: maxNodes });
  }

  getGraph(entities: string[], depth: number = 1, maxNodes: number = 25): Observable<ChatResponse['graph']> {
    return this.http.post<ChatResponse['graph']>(`${this.baseUrl}/api/graph`, { entities, depth, max_nodes: maxNodes });
  }

  getPolitician(name: string): Observable<PoliticianProfile> {
    return this.http.get<PoliticianProfile>(`${this.baseUrl}/api/politician/${encodeURIComponent(name)}`);
  }

  getAllPoliticians(): Observable<PoliticianProfile[]> {
    return this.http.get<PoliticianProfile[]>(`${this.baseUrl}/api/politicians`);
  }

  getBill(name: string): Observable<{ name: string; ementa?: string; tipo?: string; numero?: number; ano?: number }> {
    return this.http.get<{ name: string; ementa?: string; tipo?: string; numero?: number; ano?: number }>(`${this.baseUrl}/api/bill/${encodeURIComponent(name)}`);
  }

  getSuggestions(): Observable<{ popular_politicians: any[]; sample_questions: string[] }> {
    return this.http.get<{ popular_politicians: any[]; sample_questions: string[] }>(`${this.baseUrl}/api/suggestions`);
  }
}
