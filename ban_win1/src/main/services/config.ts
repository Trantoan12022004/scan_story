export interface AppSettings {
  video_dir: string
  sample_video_dir: string
  theme: string
  cms_url: string
  cms_user: string
  cms_pass: string
  deepseek_api_key?: string
}

export const DEFAULT_SETTINGS: AppSettings = {
  video_dir: 'C:\\Users\\Trant\\Videos\\Seedance\\anhtonton\\AI_VIDEO',
  sample_video_dir: 'C:\\Users\\Trant\\Videos\\short_drama',
  theme: 'dark',
  cms_url: 'https://vmnewstoryus.cfx.bz',
  cms_user: 'admin',
  cms_pass: '',
  deepseek_api_key: ''
}

export class ConfigService {
  private static cache: Record<string, string> = { ...DEFAULT_SETTINGS }

  public static get(key: string, defaultValue = ''): string {
    return this.cache[key] !== undefined ? this.cache[key] : defaultValue
  }

  public static set(key: string, value: string): void {
    this.cache[key] = value
  }

  public static setAll(settings: Record<string, string>): void {
    Object.assign(this.cache, settings)
  }

  public static videoDir(): string {
    return this.get('video_dir', DEFAULT_SETTINGS.video_dir)
  }

  public static sampleVideoDir(): string {
    return this.get('sample_video_dir', DEFAULT_SETTINGS.sample_video_dir)
  }
}
