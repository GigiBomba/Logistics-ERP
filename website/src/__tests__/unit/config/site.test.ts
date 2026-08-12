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
  it("has a baseUrl string", () => {
    expect(typeof apiConfig.baseUrl).toBe("string")
  })

  it("has a timeout", () => {
    expect(apiConfig.timeout).toBeGreaterThan(0)
  })
})

describe("downloadConfig", () => {
  it("has a version string", () => {
    expect(typeof downloadConfig.latestVersion).toBe("string")
    expect(downloadConfig.latestVersion.length).toBeGreaterThan(0)
  })

  it("has a release date", () => {
    expect(typeof downloadConfig.releaseDate).toBe("string")
  })

  it("has system requirements", () => {
    expect(downloadConfig.systemRequirements.os.length).toBeGreaterThan(0)
    expect(downloadConfig.systemRequirements.ram).toBeTruthy()
    expect(downloadConfig.systemRequirements.storage).toBeTruthy()
    expect(downloadConfig.systemRequirements.processor).toBeTruthy()
  })

  it("has a Windows installer path", () => {
    expect(typeof downloadConfig.windowsInstaller).toBe("string")
  })

  it("has a file size", () => {
    expect(typeof downloadConfig.fileSize).toBe("string")
  })
})
