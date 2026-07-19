import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { authApi, subscriptionApi, companyApi, supportApi, blogApi, changelogApi, roadmapApi, statusApi, tutorialsApi, developersApi, securityApi, announcementsApi, invoicesApi, adminBlogApi } from "@/api/endpoints"
import { useAuth } from "@/contexts/auth-provider"
import { toast } from "sonner"

// ─── Auth ────────────────────────────────────────────────────

export function useProfile() {
  const token = typeof window !== "undefined" ? localStorage.getItem("operion-access-token") : null
  return useQuery({
    queryKey: ["profile"],
    queryFn: async () => {
      const { data } = await authApi.getMe()
      return data
    },
    enabled: !!token,
  })
}

export function useUpdateProfile() {
  const queryClient = useQueryClient()
  const { updateUser } = useAuth()
  return useMutation({
    mutationFn: async (profileData: { name?: string; email?: string }) => {
      const { data } = await authApi.updateProfile(profileData)
      return data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["profile"] })
      updateUser(data as any)
    },
  })
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (data: { current_password: string; new_password: string }) => {
      await authApi.changePassword(data)
    },
  })
}

// ─── Subscription ────────────────────────────────────────────

export function useSubscription() {
  const token = typeof window !== "undefined" ? localStorage.getItem("operion-access-token") : null
  return useQuery({
    queryKey: ["subscription"],
    queryFn: async () => {
      const { data } = await subscriptionApi.getCurrent()
      return data
    },
    enabled: !!token,
  })
}

export function usePlans() {
  return useQuery({
    queryKey: ["plans"],
    queryFn: async () => {
      const { data } = await subscriptionApi.getPlans()
      return data
    },
  })
}

// ─── Company ─────────────────────────────────────────────────

export function useCompany() {
  const token = typeof window !== "undefined" ? localStorage.getItem("operion-access-token") : null
  return useQuery({
    queryKey: ["company"],
    queryFn: async () => {
      const { data } = await companyApi.get()
      return data
    },
    enabled: !!token,
  })
}

export function useUpdateCompany() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (companyData: { name?: string }) => {
      const { data } = await companyApi.update(companyData)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["company"] })
    },
  })
}

// ─── Support ─────────────────────────────────────────────────

export function useCreateTicket() {
  return useMutation({
    mutationFn: async (ticketData: { subject: string; description: string; priority?: string }) => {
      const { data } = await supportApi.createTicket(ticketData as any)
      return data
    },
  })
}

export function useTickets() {
  const token = typeof window !== "undefined" ? localStorage.getItem("operion-access-token") : null
  return useQuery({
    queryKey: ["tickets"],
    queryFn: async () => {
      const { data } = await supportApi.getTickets()
      return data
    },
    enabled: !!token,
  })
}

// ─── Blog ────────────────────────────────────────────────────

export function useBlogPosts(params?: Record<string, unknown>) {
  return useQuery({
    queryKey: ["blog-posts", params],
    queryFn: async () => {
      const { data } = await blogApi.getPosts(params as any)
      return data
    },
  })
}

export function useBlogPost(slug: string) {
  return useQuery({
    queryKey: ["blog-post", slug],
    queryFn: async () => {
      const { data } = await blogApi.getPost(slug)
      return data
    },
    enabled: !!slug,
  })
}

export function useBlogCategories() {
  return useQuery({
    queryKey: ["blog-categories"],
    queryFn: async () => {
      const { data } = await blogApi.getCategories()
      return data
    },
  })
}

// ─── Changelog ──────────────────────────────────────────────

export function useChangelog() {
  return useQuery({
    queryKey: ["changelog"],
    queryFn: async () => {
      const { data } = await changelogApi.getEntries()
      return data
    },
  })
}

// ─── Roadmap ────────────────────────────────────────────────

export function useRoadmap(status?: string) {
  return useQuery({
    queryKey: ["roadmap", status],
    queryFn: async () => {
      const { data } = await roadmapApi.getItems(status)
      return data
    },
  })
}

// ─── Service Status ─────────────────────────────────────────

export function useServiceStatus() {
  return useQuery({
    queryKey: ["service-status"],
    queryFn: async () => {
      const { data } = await statusApi.getStatus()
      return data
    },
  })
}

// ─── Tutorials ──────────────────────────────────────────────

export function useTutorials(params?: Record<string, unknown>) {
  return useQuery({
    queryKey: ["tutorials", params],
    queryFn: async () => {
      const { data } = await tutorialsApi.getTutorials(params as any)
      return data
    },
  })
}

export function useTutorial(slug: string) {
  return useQuery({
    queryKey: ["tutorial", slug],
    queryFn: async () => {
      const { data } = await tutorialsApi.getTutorial(slug)
      return data
    },
    enabled: !!slug,
  })
}

// ─── Developer Resources ────────────────────────────────────

export function useDevResources() {
  return useQuery({
    queryKey: ["dev-resources"],
    queryFn: async () => {
      const { data } = await developersApi.getResources()
      return data
    },
  })
}

export function useToolkitVersions() {
  return useQuery({
    queryKey: ["toolkit-versions"],
    queryFn: async () => {
      const { data } = await developersApi.getToolkitVersions()
      return data
    },
  })
}

// ─── Security Reports ──────────────────────────────────────

export function useSecurityReports() {
  return useQuery({
    queryKey: ["security-reports"],
    queryFn: async () => {
      const { data } = await securityApi.getReports()
      return data
    },
  })
}

export function useSubmitSecurityReport() {
  return useMutation({
    mutationFn: async (reportData: { title: string; description: string; severity: string }) => {
      const { data } = await securityApi.submitReport(reportData)
      return data
    },
  })
}

// ─── Announcements ──────────────────────────────────────────

export function useAnnouncements() {
  return useQuery({
    queryKey: ["announcements"],
    queryFn: async () => {
      const { data } = await announcementsApi.getAnnouncements()
      return data
    },
  })
}

// ─── Invoices ──────────────────────────────────────────────

export function useInvoices() {
  return useQuery({
    queryKey: ["invoices"],
    queryFn: async () => {
      const { data } = await invoicesApi.getInvoices()
      return data
    },
  })
}

// ─── Admin Blog ────────────────────────────────────────────

export function useCreateBlogPost() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (postData: Record<string, unknown>) => {
      const { data } = await adminBlogApi.createPost(postData as any)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["blog-posts"] })
    },
    onError: () => {
      toast.error("Failed to create post")
    },
  })
}

export function useUpdateBlogPost() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ slug, ...data }: Record<string, unknown>) => {
      const { data: result } = await adminBlogApi.updatePost(slug as string, data as any)
      return result
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["blog-posts"] })
    },
  })
}

export function useDeleteBlogPost() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (slug: string) => {
      await adminBlogApi.deletePost(slug)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["blog-posts"] })
    },
  })
}

// ─── Organizations ────────────────────────────────────────────

// TODO: Implement when backend endpoint is ready
export function useOrganizations() {
  return { data: [] as any[], isLoading: false, isError: false }
}

// TODO: Implement when backend endpoint is ready
export function useOrganization(_slug: string) {
  return { data: undefined, isLoading: false, isError: false }
}

// TODO: Implement when backend endpoint is ready
export function useCreateOrganization() {
  return { mutate: (..._args: any[]) => {}, mutateAsync: (..._args: any[]) => Promise.resolve({}), isPending: false }
}

// TODO: Implement when backend endpoint is ready
export function useUpdateOrganization() {
  return { mutate: (..._args: any[]) => {}, mutateAsync: (..._args: any[]) => Promise.resolve({}), isPending: false }
}

// TODO: Implement when backend endpoint is ready
export function useOrganizationMembers(_slug: string) {
  return { data: [] as any[], isLoading: false, isError: false }
}

// TODO: Implement when backend endpoint is ready
export function useInviteMember() {
  return { mutate: (..._args: any[]) => {}, mutateAsync: (..._args: any[]) => Promise.resolve({}), isPending: false }
}

// TODO: Implement when backend endpoint is ready
export function useRemoveMember() {
  return { mutate: (..._args: any[]) => {}, mutateAsync: (..._args: any[]) => Promise.resolve({}), isPending: false }
}

// ─── Licensing ────────────────────────────────────────────────

// TODO: Implement when backend endpoint is ready
export function useLicenses() {
  return { data: [] as any[], isLoading: false, isError: false }
}

// ─── Onboarding ───────────────────────────────────────────────

// TODO: Implement when backend endpoint is ready
export function useOnboardingChecklist() {
  return { data: [] as any[], isLoading: false, isError: false }
}

// TODO: Implement when backend endpoint is ready
export function useCompleteOnboardingStep() {
  return { mutate: (..._args: any[]) => {}, mutateAsync: (..._args: any[]) => Promise.resolve({}), isPending: false }
}

// ─── Integrations ─────────────────────────────────────────────

// TODO: Implement when backend endpoint is ready
export function useIntegrations(_category?: string) {
  return { data: [] as any[], isLoading: false, isError: false }
}

// ─── Customer Stories ─────────────────────────────────────────

// TODO: Implement when backend endpoint is ready
export function useCustomerStories(_params?: Record<string, unknown>) {
  return { data: [] as any[], isLoading: false, isError: false }
}

// TODO: Implement when backend endpoint is ready
export function useCustomerStory(_slug: string) {
  return { data: undefined, isLoading: false, isError: false }
}

// ─── Press ────────────────────────────────────────────────────

// TODO: Implement when backend endpoint is ready
export function usePressReleases() {
  return { data: [] as any[], isLoading: false, isError: false }
}

// TODO: Implement when backend endpoint is ready
export function usePressKit() {
  return { data: undefined, isLoading: false, isError: false }
}

// ─── Partners ─────────────────────────────────────────────────

// TODO: Implement when backend endpoint is ready
export function usePartners(_type?: string) {
  return { data: [] as any[], isLoading: false, isError: false }
}

// ─── Newsletter ───────────────────────────────────────────────

// TODO: Implement when backend endpoint is ready
export function useSubscribeNewsletter() {
  return { mutate: (..._args: any[]) => {}, mutateAsync: (..._args: any[]) => Promise.resolve({}), isPending: false }
}

// ─── Global Search ────────────────────────────────────────────

// TODO: Implement when backend endpoint is ready
export function useGlobalSearch(_query: string, _type?: string) {
  return { data: [] as any[], isLoading: false, isError: false }
}

// ─── Portal Notifications ─────────────────────────────────────

// TODO: Implement when backend endpoint is ready
export function usePortalNotifications() {
  return { data: [] as any[], isLoading: false, isError: false }
}

// TODO: Implement when backend endpoint is ready
export function useMarkNotificationRead() {
  return { mutate: (..._args: any[]) => {}, mutateAsync: (..._args: any[]) => Promise.resolve({}), isPending: false }
}

// TODO: Implement when backend endpoint is ready
export function useUpdateNotificationPreferences() {
  return { mutate: (..._args: any[]) => {}, mutateAsync: (..._args: any[]) => Promise.resolve({}), isPending: false }
}
