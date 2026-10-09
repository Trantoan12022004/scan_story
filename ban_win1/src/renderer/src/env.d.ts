/// <reference types="vite/client" />
import type { IpcApi } from '../../preload'

declare global {
  interface Window {
    api: IpcApi
  }
}
