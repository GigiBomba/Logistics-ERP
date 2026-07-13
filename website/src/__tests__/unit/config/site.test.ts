import { describe, it, expect } from "vitest"
import { siteConfig, apiConfig, downloadConfig } from "@/config/site"

describe("siteConfig", () => {
  it("has required fields", () => {
    expect(siteConfig.name).toBe("Operion")
    expect(siteConfig.tagline).toBeTruthy()
    expect(siteConfig.description).toBeTruthy()
    expect(siteConfig.url).toMatch(/^https?:\/\//)
  })

  it("has links object", () => {
    expect(siteConfig.links.twitter).toBeTruthy()
    expect(siteConfig.links.github).toBeTruthy()
    expect(siteConfig.links.linkedin).toBeTruthy()
  })
})

describe("apiConfig", () => {
  it("defaults to localhost:8000", () => {
    expect(apiConfig.baseUrl).toBe("http://localhost:8000")
  })

  it("has a timeout", () => {
    expect(apiConfig.timeout).toBeGreaterThan(0)
  })
})

describe("downloadConfig", () => {
  it("has a version string", () => {
    expect(downloadConfig.latestVersion).toMatch(/^\d+\.\d+\.\d+$/)
  })

  it("has a release date", () => {
    expect(downloadConfig.releaseDate).toBeTruthy()
    expect(() => new Date(downloadConfig.releaseDate)).not.toThrow()
  })

  it("has system requirements", () => {
    expect(downloadConfig.systemRequirements.os.length).toBeGreaterThan(0)
    expect(downloadConfig.systemRequirements.ram).toBeTruthy()
    expect(downloadConfig.systemRequirements.storage).toBeTruthy()
    expect(downloadConfig.systemRequirements.processor).toBeTruthy()
  })

  it("has a Windows installer path", () => {
    expect(downloadConfig.windowsInstaller).toBe("#")
  })

  it("has a file size", () => {
    expect(downloadConfig.fileSize).toBe("TBD")
  })
})
