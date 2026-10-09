import fs from 'fs'
import path from 'path'

export function getBinaryPath(binaryName: string): string {
  const exeName = process.platform === 'win32' ? `${binaryName}.exe` : binaryName

  // 1. Packaged Electron resources
  const resourcesPath = (process as any).resourcesPath
  if (resourcesPath) {
    const packagedPath = path.join(resourcesPath, 'bin', exeName)
    if (fs.existsSync(packagedPath)) {
      return packagedPath
    }
  }

  // 2. Development project resources/bin
  const devPath = path.join(process.cwd(), 'resources', 'bin', exeName)
  if (fs.existsSync(devPath)) {
    return devPath
  }

  // 3. System PATH fallback
  return exeName
}
