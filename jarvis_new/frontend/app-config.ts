export interface AppConfig {
  pageTitle: string;
  pageDescription: string;
  companyName: string;

  supportsChatInput: boolean;
  supportsVideoInput: boolean;
  supportsScreenShare: boolean;
  isPreConnectBufferEnabled: boolean;

  logo: string;
  startButtonText: string;
  accent?: string;
  logoDark?: string;
  accentDark?: string;

  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorDark?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerBarCount?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerWaveLineWidth?: number;

  // agent dispatch configuration
  agentName?: string;

  // LiveKit Cloud Sandbox configuration
  sandboxId?: string;
}

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: 'Jarvis',
  pageTitle: 'Jarvis | Your voice butler',
  pageDescription: 'A private voice butler for getting things done.',

  supportsChatInput: true,
  supportsVideoInput: true,
  supportsScreenShare: true,
  isPreConnectBufferEnabled: true,

  logo: '/lk-logo.svg',
  accent: '#16d9c5',
  logoDark: '/lk-logo-dark.svg',
  accentDark: '#73f7e4',
  startButtonText: 'Begin private session',

  // optional: audio visualization configuration
  // audioVisualizerType: 'bar',
  audioVisualizerColor: '#002cf2',
  audioVisualizerColorDark: '#1fd5f9',
  // audioVisualizerColorShift: 0.3,
  // audioVisualizerBarCount: 5,
  //audioVisualizerType: 'radial',
  //audioVisualizerRadialBarCount: 24,
  //audioVisualizerRadialRadius: 100,
  //audioVisualizerType: 'grid',
  //audioVisualizerGridRowCount: 25,
  //audioVisualizerGridColumnCount: 25,
  //audioVisualizerType: 'wave',
  //audioVisualizerWaveLineWidth: 3,
  audioVisualizerType: 'aura',

  // agent dispatch configuration
  agentName: process.env.AGENT_NAME || 'my-agent',

  // LiveKit Cloud Sandbox configuration
  sandboxId: undefined,
};
