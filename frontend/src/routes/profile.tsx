import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Activity, Flame, MessageCircle, Pencil, Plus, Save, Send, Target, Trash2, User as UserIcon, Wallet, X } from "lucide-react";
import { toast } from "sonner";
import { storage } from "@/lib/storage";
import { api, type FamilyMember, type OnboardPayload } from "@/lib/api";

export const Route = createFileRoute("/profile")({
  component: Profile,
});

const DIET_OPTIONS = ["Vegetarian", "Eggetarian", "Vegan", "Non-vegetarian", "Pescatarian", "Keto"];
const GOALS = [
  { value: "weight_loss", label: "Weight loss" },
  { value: "muscle_gain", label: "Muscle gain" },
  { value: "maintenance", label: "Maintenance" },
] as const;

function Profile() {
  const [profile, setProfile] = useState<OnboardPayload | null>(null);
  const [savedProfile, setSavedProfile] = useState<OnboardPayload | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingTelegram, setTestingTelegram] = useState(false);
  const [testingWhatsapp, setTestingWhatsapp] = useState(false);
  const [familyConnecting, setFamilyConnecting] = useState("");
  const [streak, setStreak] = useState(0);

  useEffect(() => {
    const loadedProfile = storage.getProfile<OnboardPayload>() || {
      name: storage.getUserName() || "Guest",
      age: 0,
      gender: "",
      weight: 0,
      height: 0,
      goal: "maintenance",
      weekly_budget: 0,
      telegram: storage.getTelegram() || "",
      whatsapp: storage.getWhatsapp() || "",
      dietary_preference: "",
      allergies: [],
      preferences: [],
      family: [],
    };
    setProfile(loadedProfile);
    setSavedProfile(loadedProfile);
    setStreak(storage.getStreak());
    const userId = storage.getUserId();
    if (userId) {
      api.getProfile(userId).then((result) => {
        const freshProfile = normalizeProfile(result.profile);
        setProfile(freshProfile);
        setSavedProfile(freshProfile);
        storage.setProfile(freshProfile);
        storage.setUserName(freshProfile.name);
        storage.setGoal(freshProfile.goal);
        storage.setCredits(Number(result.profile.credits ?? storage.getCredits()));
        storage.setRole(result.profile.role || storage.getRole());
        storage.setTelegram(freshProfile.telegram || "");
        storage.setWhatsapp(freshProfile.whatsapp || "");
      }).catch(() => {});
      api.getStreak(userId).then((result) => {
        storage.setStreak(result.streak);
        setStreak(result.streak);
      }).catch(() => {});
    }
  }, []);

  if (!profile) return null;

  const update = (patch: Partial<OnboardPayload>) => setProfile((p) => p ? { ...p, ...patch } : p);
  const family = profile.family ?? [];
  const errors = validateProfile(profile);
  const familyErrors = validateFamily(family);
  const budgetIsValid = !errors.weekly_budget;
  const profileIsValid = Object.keys(errors).length === 0 && Object.keys(familyErrors).length === 0;
  const bmi = profile.weight && profile.height ? (profile.weight / Math.pow(profile.height / 100, 2)).toFixed(1) : "-";
  const initials = (profile.name || "U").split(" ").map((s: string) => s[0]).join("").slice(0, 2).toUpperCase();

  function patchFamily(index: number, patch: Partial<FamilyMember>) {
    update({ family: family.map((m, i) => (i === index ? { ...m, ...patch } : m)) });
  }

  function addFamily() {
    update({ family: [...family, { name: "", age: 0, goal: "" as FamilyMember["goal"], gender: "", weight: 0, height: 0, diet: "", allergies: [], preferences: [], telegram: "", whatsapp: "" }] });
  }

  function removeFamily(index: number) {
    update({ family: family.filter((_, i) => i !== index) });
  }

  async function save() {
    if (!profileIsValid) {
      toast.error("Please fix profile details", { description: Object.values(errors)[0] || Object.values(familyErrors)[0] });
      return;
    }
    setSaving(true);
    try {
      const userId = storage.getUserId();
      const payload = sanitizeProfile(profile);
      if (userId) {
        const result = await api.updateProfile(userId, payload);
        const updatedProfile = normalizeProfile(result.profile);
        setProfile(updatedProfile);
        storage.setProfile(updatedProfile);
        storage.setUserName(updatedProfile.name);
        storage.setGoal(updatedProfile.goal);
        storage.setTelegram(updatedProfile.telegram || "");
        storage.setWhatsapp(updatedProfile.whatsapp || "");
        setSavedProfile(updatedProfile);
      } else {
        storage.setProfile(payload);
        storage.setUserName(payload.name);
        storage.setGoal(payload.goal);
        storage.setTelegram(payload.telegram || "");
        storage.setWhatsapp(payload.whatsapp || "");
        setSavedProfile(payload);
      }
      setIsEditing(false);
      toast.success("Profile updated");
    } catch (error) {
      toast.error("Profile was not saved", { description: error instanceof Error ? error.message : "Please try again." });
    } finally {
      setSaving(false);
    }
  }

  async function saveForTest() {
    if (!profileIsValid) {
      toast.error("Please fix profile details", { description: Object.values(errors)[0] || Object.values(familyErrors)[0] });
      return false;
    }
    const userId = storage.getUserId();
    if (!userId) {
      toast.error("Create profile first");
      return false;
    }
    const payload = sanitizeProfile(profile);
    const result = await api.updateProfile(userId, payload);
    const updatedProfile = normalizeProfile(result.profile);
    setProfile(updatedProfile);
    storage.setProfile(updatedProfile);
    storage.setUserName(updatedProfile.name);
    storage.setGoal(updatedProfile.goal);
    storage.setTelegram(updatedProfile.telegram || "");
    storage.setWhatsapp(updatedProfile.whatsapp || "");
    setSavedProfile(updatedProfile);
    return true;
  }

  async function testTelegram() {
    const userId = storage.getUserId();
    if (!userId) {
      toast.error("Create profile first");
      return;
    }
    if (!profile.telegram?.trim()) {
      toast.error("Telegram chat ID missing", { description: "Enter the Telegram chat ID first." });
      return;
    }
    setTestingTelegram(true);
    try {
      const saved = await saveForTest();
      if (!saved) return;
      await api.testTelegram(userId);
      toast.success("Test message sent", { description: "Check Telegram for the Smart Meal AI message." });
    } catch (error) {
      toast.error("Telegram test failed", { description: error instanceof Error ? error.message : "Please check the chat ID and bot token." });
    } finally {
      setTestingTelegram(false);
    }
  }

  async function openTelegramBot() {
    try {
      const result = await api.getTelegramBotLink();
      window.open(result.url, "_blank", "noopener,noreferrer");
      toast.success("Telegram bot opened", { description: "Tap Start, copy the chat ID, then paste it here." });
    } catch (error) {
      toast.error("Could not open bot", { description: error instanceof Error ? error.message : "Please check Telegram bot setup." });
    }
  }

  async function copyTelegramInvite(name?: string) {
    const person = name?.trim() || "there";
    const message = `Hi ${person}, please connect Telegram for Smart Meal AI:\n\n1. Open this bot link:\nhttps://t.me/cooking_agent_1892_bot\n\n2. Tap Start or send /start\n\n3. The bot will reply with a Telegram chat ID.\n\n4. Send that chat ID back to me.\n\nI will add it to your Smart Meal AI family profile so you can approve/reject your own meal plan.`;
    try {
      await navigator.clipboard.writeText(message);
      toast.success("Invite copied", { description: "Send it to the family member." });
    } catch {
      toast.error("Could not copy invite");
    }
  }

  async function testWhatsapp() {
    const cleanedWhatsapp = String(profile.whatsapp || "").replace(/\D/g, "");
    if (!cleanedWhatsapp) {
      toast.error("WhatsApp number missing", { description: "Paste your WhatsApp number with country code first." });
      return;
    }
    if (cleanedWhatsapp.length < 10) {
      toast.error("Enter a valid WhatsApp number", { description: "Use country code, no +. Example: 919876543210" });
      return;
    }
    const userId = storage.getUserId();
    if (!userId) {
      toast.error("Create profile first");
      return;
    }
    setTestingWhatsapp(true);
    try {
      update({ whatsapp: cleanedWhatsapp });
      const saved = await saveForTest();
      if (!saved) return;
      await api.testWhatsapp(userId);
      toast.success("WhatsApp connected", { description: "A test message was sent." });
    } catch (error) {
      toast.error("WhatsApp test failed", { description: error instanceof Error ? error.message : "Please check Meta setup and recipient number." });
    } finally {
      setTestingWhatsapp(false);
    }
  }

  async function testFamilyContact(channel: "Telegram" | "WhatsApp", value: string | undefined, key: string, telegramValue?: string) {
    const cleanValue = channel === "WhatsApp"
      ? String(value || "").replace(/\D/g, "")
      : String(value || "").trim();
    if (!cleanValue) {
      toast.error(`${channel} value missing`, {
        description: channel === "Telegram" ? "Paste the Telegram chat ID first." : "Paste the WhatsApp number with country code first.",
      });
      return;
    }
    if (channel === "WhatsApp") {
      const cleanTelegram = String(telegramValue || "").replace(/\D/g, "");
      if (cleanTelegram && cleanTelegram === cleanValue) {
        toast.error("Use WhatsApp number here", { description: "This looks like the Telegram chat ID. Enter WhatsApp number with country code." });
        return;
      }
    }
    setFamilyConnecting(key);
    try {
      if (channel === "Telegram") await api.testTelegramContact(cleanValue);
      else await api.testWhatsappContact(cleanValue);
      toast.success(`${channel} connected`, { description: "A test message was sent." });
    } catch (error) {
      toast.error(`${channel} connection failed`, { description: error instanceof Error ? error.message : "Please check the value and try again." });
    } finally {
      setFamilyConnecting("");
    }
  }

  function cancelEdit() {
    if (savedProfile) setProfile(savedProfile);
    setIsEditing(false);
  }

  return (
    <div className="space-y-8 animate-fade-up">
      <header className="rounded-2xl border border-border bg-surface shadow-soft p-6 sm:p-8 flex flex-wrap items-center gap-6">
        <div className="size-20 rounded-2xl hero-gradient text-white text-2xl font-semibold grid place-items-center shadow-glow">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight truncate">{profile.name || "Guest"}</h1>
          <p className="text-sm text-text-secondary capitalize mt-0.5">
            {String(profile.goal).replace("_", " ")} · {streak}-week planning streak
          </p>
        </div>
        {isEditing ? (
          <div className="flex flex-wrap gap-2">
            <button onClick={cancelEdit} className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-medium hover:bg-muted transition">
              <X className="size-4" /> Cancel
            </button>
            <button
              onClick={save}
              disabled={!profileIsValid || saving}
              className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium hover:opacity-90 transition shadow-soft disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save className="size-4" /> {saving ? "Saving..." : "Save profile"}
            </button>
          </div>
        ) : (
          <button onClick={() => setIsEditing(true)} className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium hover:opacity-90 transition shadow-soft">
            <Pencil className="size-4" /> Edit profile
          </button>
        )}
      </header>

      <section className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-4">
        <Stat icon={Target} label="Weight" value={profile.weight ? `${profile.weight} kg` : "Not set"} />
        <Stat icon={Activity} label="Height" value={profile.height ? `${profile.height} cm` : "Not set"} />
        <Stat icon={Flame} label="BMI" value={bmi} />
        <Stat icon={UserIcon} label="Age" value={profile.age ? `${profile.age}` : "Not set"} />
        <Stat icon={Wallet} label="Meal Budget" value={profile.weekly_budget ? `₹${profile.weekly_budget}` : "Not set"} tone={budgetIsValid ? "default" : "error"} />
      </section>
      {!budgetIsValid && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          Weekly meal budget is too low. Enter at least ₹1500 before saving or generating a meal plan.
        </div>
      )}

      {!isEditing && (
        <>
          <section className="rounded-2xl border border-border bg-surface shadow-soft p-6">
            <h2 className="text-sm font-semibold">Profile details</h2>
            <div className="mt-5 grid sm:grid-cols-2 gap-3">
              <Detail label="Goal" value={String(profile.goal).replace("_", " ")} />
              <Detail label="Gender" value={profile.gender || "Not set"} />
              <Detail label="Dietary preference" value={profile.dietary_preference || "Not set"} />
              <Detail label="Weekly meal budget" value={profile.weekly_budget ? `₹${profile.weekly_budget}` : "Not set"} />
              <Detail label="Telegram chat ID" value={profile.telegram || "Not added"} />
              <Detail label="WhatsApp number" value={profile.whatsapp || "Not added"} />
              <Detail label="Allergies" value={(profile.allergies ?? []).join(", ") || "None"} />
              <Detail label="Preferences" value={(profile.preferences ?? []).join(", ") || "None"} />
            </div>
          </section>

          <section className="rounded-2xl border border-border bg-surface shadow-soft p-6">
            <h2 className="text-sm font-semibold">Family members</h2>
            <div className="mt-5 space-y-3">
              {family.length === 0 && <div className="text-sm text-text-light rounded-xl border border-dashed border-border p-6 text-center">No family members yet.</div>}
              {family.map((member, index) => (
                <div key={index} className="rounded-xl border border-border p-4">
                  <div className="font-medium">{member.name || `Family member ${index + 1}`}</div>
                  <div className="mt-1 text-sm text-text-secondary capitalize">
                    {member.goal?.replace("_", " ") || "Not set"} · {member.diet || "Not set"}
                  </div>
                  <div className="mt-3 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    <Detail label="Stats" value={`${member.gender || "Not set"} · ${member.age || "-"}y · ${(member.weight ?? member.weight_kg) || "-"}kg · ${(member.height ?? member.height_cm) || "-"}cm`} compact />
                    <Detail label="Allergies" value={(member.allergies ?? []).join(", ") || "None"} compact />
                    <Detail label="Preferences" value={(member.preferences ?? []).join(", ") || "None"} compact />
                    <Detail label="Telegram" value={member.telegram || "Not added"} compact />
                    <Detail label="WhatsApp" value={member.whatsapp || "Not added"} compact />
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {isEditing && <section className="rounded-2xl border border-border bg-surface shadow-soft p-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">Main profile</h2>
            <p className="text-xs text-text-light mt-0.5">Update the profile details used by the app UI.</p>
          </div>
        </div>
        <div className="mt-5 grid sm:grid-cols-2 gap-4">
          <Field label="Full name">
            <input className={input()} value={profile.name} onChange={(e) => update({ name: e.target.value })} />
            {errors.name && <ErrorText>{errors.name}</ErrorText>}
          </Field>
          <Field label="Goal">
            <select className={input()} value={profile.goal} onChange={(e) => update({ goal: e.target.value as OnboardPayload["goal"] })}>
              {GOALS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
            </select>
            {errors.goal && <ErrorText>{errors.goal}</ErrorText>}
          </Field>
          <Field label="Age">
            <input type="number" className={input()} value={profile.age || ""} onChange={(e) => update({ age: cleanNumber(e.target.value) })} />
            {errors.age && <ErrorText>{errors.age}</ErrorText>}
          </Field>
          <Field label="Gender">
            <select className={input()} value={profile.gender ?? ""} onChange={(e) => update({ gender: e.target.value })}>
              <option value="">Prefer not to say</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </select>
          </Field>
          <Field label="Weight (kg)">
            <input type="number" className={input()} value={profile.weight || ""} onChange={(e) => update({ weight: cleanNumber(e.target.value) })} />
            {errors.weight && <ErrorText>{errors.weight}</ErrorText>}
          </Field>
          <Field label="Height (cm)">
            <input type="number" className={input()} value={profile.height || ""} onChange={(e) => update({ height: cleanNumber(e.target.value) })} />
            {errors.height && <ErrorText>{errors.height}</ErrorText>}
          </Field>
          <Field label="Weekly meal budget (INR)" hint="Minimum ₹1500. ₹2500 is a good starting weekly budget.">
            <input type="number" min={1500} step={100} className={input()} value={profile.weekly_budget || ""} onChange={(e) => update({ weekly_budget: cleanNumber(e.target.value) })} />
            {errors.weekly_budget && <ErrorText>{errors.weekly_budget}</ErrorText>}
          </Field>
          <Field label="Dietary preference">
            <select className={input()} value={profile.dietary_preference ?? ""} onChange={(e) => update({ dietary_preference: e.target.value })}>
              <option value="">Select dietary preference</option>
              {DIET_OPTIONS.map((diet) => <option key={diet}>{diet}</option>)}
            </select>
            {errors.dietary_preference && <ErrorText>{errors.dietary_preference}</ErrorText>}
          </Field>
          <Field label="Telegram chat ID" hint="Enter the chat ID from Telegram. Use Send test to verify it.">
            <div className="flex gap-2">
              <input className={input()} value={profile.telegram ?? ""} onChange={(e) => update({ telegram: e.target.value.replace(/[^\d-]/g, "") })} placeholder="e.g. 8892259333" />
              <button type="button" onClick={testTelegram} disabled={testingTelegram || saving} className={connectButtonClass()}>
                <Send className="size-4" /> {testingTelegram ? "Sending" : "Send test"}
              </button>
            </div>
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-text-light">
              <button type="button" onClick={openTelegramBot} className="text-primary font-medium hover:underline">Open bot</button>
              <span>Tap Start or send /start. The bot replies with your chat ID; paste that number here.</span>
            </div>
          </Field>
          <Field label="WhatsApp number" hint="Use country code, no +. Example: 919876543210">
            <input className={input()} value={profile.whatsapp ?? ""} onChange={(e) => update({ whatsapp: e.target.value.replace(/\D/g, "") })} placeholder="Optional" />
            <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-warning">
              <span className="inline-flex items-center gap-1 rounded-md border border-warning/30 bg-warning/10 px-2 py-1 font-medium"><MessageCircle className="size-3" /> Coming soon</span>
              <span>You can save the number now; WhatsApp approvals will be enabled later.</span>
            </div>
          </Field>
          <Field label="Allergies">
            <input className={input()} value={(profile as any)._allergiesText ?? (profile.allergies ?? []).join(", ")} onChange={(e) => update({ allergies: splitList(e.target.value), _allergiesText: e.target.value } as any)} placeholder="Optional" />
          </Field>
          <Field label="Preferences">
            <input className={input()} value={(profile as any)._preferencesText ?? (profile.preferences ?? []).join(", ")} onChange={(e) => update({ preferences: splitList(e.target.value), _preferencesText: e.target.value } as any)} placeholder="Optional" />
          </Field>
        </div>
      </section>}

      {isEditing && <section className="rounded-2xl border border-border bg-surface shadow-soft p-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">Family members</h2>
            <p className="text-xs text-text-light mt-0.5">Edit everyone included in meal planning.</p>
          </div>
          <button onClick={addFamily} className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-2 text-sm font-medium hover:bg-muted transition">
            <Plus className="size-4" /> Add family member
          </button>
        </div>

        <div className="mt-5 space-y-3">
          {family.length === 0 && <div className="text-sm text-text-light rounded-xl border border-dashed border-border p-6 text-center">No family members yet.</div>}
          {family.map((member, index) => (
            <div key={index} className="rounded-xl border border-border p-4">
              <div className="flex flex-col gap-4">
                <div className="grid sm:grid-cols-2 gap-3 flex-1">
                  <Field label="Name">
                    <input className={input()} value={member.name} onChange={(e) => patchFamily(index, { name: e.target.value })} />
                    {familyErrors[index] && <ErrorText>{familyErrors[index]}</ErrorText>}
                  </Field>
                  <Field label="Dietary preference">
                    <select className={input()} value={member.diet ?? ""} onChange={(e) => patchFamily(index, { diet: e.target.value })}>
                      <option value="">Select dietary preference</option>
                      {DIET_OPTIONS.map((diet) => <option key={diet}>{diet}</option>)}
                    </select>
                  </Field>
                  <Field label="Goal">
                    <select className={input()} value={member.goal ?? ""} onChange={(e) => patchFamily(index, { goal: e.target.value as FamilyMember["goal"] })}>
                      <option value="">Select goal</option>
                      <option value="weight_loss">Weight Loss</option>
                      <option value="muscle_gain">Muscle Gain</option>
                      <option value="maintenance">Maintenance</option>
                    </select>
                  </Field>
                  <Field label="Gender">
                    <select className={input()} value={member.gender ?? ""} onChange={(e) => patchFamily(index, { gender: e.target.value })}>
                      <option value="">Prefer not to say</option>
                      <option value="female">Female</option>
                      <option value="male">Male</option>
                      <option value="other">Other</option>
                    </select>
                  </Field>
                  <Field label="Age">
                    <input className={input()} type="number" value={member.age || ""} onChange={(e) => patchFamily(index, { age: cleanNumber(e.target.value) })} />
                  </Field>
                  <Field label="Weight (kg)">
                    <input className={input()} type="number" value={(member.weight ?? member.weight_kg) || ""} onChange={(e) => patchFamily(index, { weight: cleanNumber(e.target.value) })} />
                  </Field>
                  <Field label="Height (cm)">
                    <input className={input()} type="number" value={(member.height ?? member.height_cm) || ""} onChange={(e) => patchFamily(index, { height: cleanNumber(e.target.value) })} />
                  </Field>
                  <Field label="Allergies">
                    <input className={input()} value={(member as any)._allergiesText ?? (member.allergies ?? []).join(", ")} onChange={(e) => patchFamily(index, { allergies: splitList(e.target.value), _allergiesText: e.target.value } as any)} placeholder="Optional" />
                  </Field>
                  <Field label="Preferences">
                    <input className={input()} value={(member as any)._preferencesText ?? (member.preferences ?? []).join(", ")} onChange={(e) => patchFamily(index, { preferences: splitList(e.target.value), _preferencesText: e.target.value } as any)} placeholder="Optional" />
                  </Field>
                  <Field label="Telegram chat ID">
                    <div className="flex gap-2">
                      <input className={input()} value={member.telegram ?? ""} onChange={(e) => patchFamily(index, { telegram: e.target.value.replace(/[^\d-]/g, "") })} placeholder="e.g. 8892259333" />
                      <button type="button" onClick={() => testFamilyContact("Telegram", member.telegram, `telegram-${index}`)} disabled={familyConnecting !== ""} className={connectButtonClass()}>
                        <Send className="size-4" /> {familyConnecting === `telegram-${index}` ? "Sending" : "Send test"}
                      </button>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-text-light">
                      <button type="button" onClick={openTelegramBot} className="text-primary font-medium hover:underline">Open bot</button>
                      <button type="button" onClick={() => copyTelegramInvite(member.name)} className="text-primary font-medium hover:underline">Copy invite</button>
                      <span>They open bot, tap Start or send /start, then send you the chat ID shown by the bot.</span>
                    </div>
                  </Field>
                  <Field label="WhatsApp number">
                    <input className={input()} value={member.whatsapp ?? ""} onChange={(e) => patchFamily(index, { whatsapp: e.target.value.replace(/\D/g, "") })} placeholder="Optional" />
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-warning">
                      <span className="inline-flex items-center gap-1 rounded-md border border-warning/30 bg-warning/10 px-2 py-1 font-medium"><MessageCircle className="size-3" /> Coming soon</span>
                      <span>Saved now for future WhatsApp approvals.</span>
                    </div>
                  </Field>
                </div>
                <button onClick={() => removeFamily(index)} className="self-start inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-medium text-text-secondary hover:text-destructive hover:border-destructive/30 hover:bg-destructive/5 transition">
                  <Trash2 className="size-3.5" /> Delete family member
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>}
    </div>
  );
}

function normalizeProfile(raw: any): OnboardPayload {
  return {
    name: raw?.name || "",
    email: raw?.email || "",
    age: Number(raw?.age || 0),
    gender: raw?.gender || "",
    weight: Number(raw?.weight ?? raw?.weight_kg ?? 0),
    height: Number(raw?.height ?? raw?.height_cm ?? 0),
    goal: raw?.goal || "maintenance",
    weekly_budget: Number(raw?.weekly_budget ?? raw?.budget_weekly ?? 0),
    telegram: raw?.telegram ?? raw?.telegram_id ?? "",
    whatsapp: raw?.whatsapp ?? raw?.whatsapp_number ?? "",
    dietary_preference: raw?.dietary_preference ?? raw?.dietary_type ?? "",
    allergies: raw?.allergies || [],
    preferences: raw?.preferences || [],
    family: (raw?.family || []).map((member: any) => ({
      id: member.id,
      name: member.name || "",
      age: Number(member.age || 0),
      goal: member.goal || "maintenance",
      gender: member.gender || "",
      weight: Number(member.weight ?? member.weight_kg ?? 0),
      height: Number(member.height ?? member.height_cm ?? 0),
      diet: member.diet ?? member.dietary_type ?? "",
      allergies: member.allergies || [],
      preferences: member.preferences || [],
      telegram: member.telegram || "",
      whatsapp: member.whatsapp || member.whatsapp_number || "",
    })),
  };
}

function splitList(value: string) {
  return value.split(",").map((s) => s.trim()).filter(Boolean);
}

function sanitizeProfile(profile: OnboardPayload): OnboardPayload {
  const { _allergiesText, _preferencesText, ...cleanProfile } = profile as any;
  return {
    ...cleanProfile,
    whatsapp_number: profile.whatsapp || profile.whatsapp_number || "",
    allergies: profile.allergies ?? [],
    preferences: profile.preferences ?? [],
    family: (profile.family ?? [])
      .filter((member) => member.name?.trim())
      .map(({ _allergiesText, _preferencesText, ...member }: any) => ({
        ...member,
        whatsapp_number: member.whatsapp || member.whatsapp_number || "",
        allergies: member.allergies ?? [],
        preferences: member.preferences ?? [],
      })),
  };
}

function input() {
  return "w-full rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm placeholder:text-text-light focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/40 transition";
}

function connectButtonClass() {
  return "shrink-0 inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm font-medium hover:opacity-90 transition shadow-soft disabled:opacity-50 disabled:cursor-not-allowed";
}

function isValidBudget(value: unknown) {
  const budget = Number(value || 0);
  return budget >= 1500;
}

function validateProfile(profile: OnboardPayload) {
  const errors: Record<string, string> = {};
  if (!profile.name?.trim()) errors.name = "Full name is required.";
  if (!profile.goal) errors.goal = "Goal is required.";
  if (!profile.dietary_preference) errors.dietary_preference = "Dietary preference is required.";
  if (!Number.isFinite(Number(profile.age)) || profile.age < 1 || profile.age > 120) errors.age = "Enter a valid age.";
  if (!Number.isFinite(Number(profile.weight)) || profile.weight < 20 || profile.weight > 300) errors.weight = "Enter a valid weight.";
  if (!Number.isFinite(Number(profile.height)) || profile.height < 80 || profile.height > 250) errors.height = "Enter a valid height.";
  if (!isValidBudget(profile.weekly_budget)) errors.weekly_budget = "Budget is too low. Please enter at least ₹1500.";
  return errors;
}

function validateFamily(family: FamilyMember[]) {
  const errors: Record<number, string> = {};
  family.forEach((member, index) => {
    if (!member.name?.trim()) errors[index] = "Family member name is required. Delete this row if you do not want to add them.";
    if (!member.diet) errors[index] = "Dietary preference is required.";
    if (!member.goal) errors[index] = "Goal is required for each family member.";
    if (member.age && (member.age < 1 || member.age > 120)) errors[index] = "Enter a valid age for each family member.";
    const weight = Number(member.weight ?? member.weight_kg ?? 0);
    const height = Number(member.height ?? member.height_cm ?? 0);
    if (weight && (weight < 20 || weight > 300)) errors[index] = "Enter a valid weight for each family member.";
    if (height && (height < 80 || height > 250)) errors[index] = "Enter a valid height for each family member.";
  });
  return errors;
}

function cleanNumber(value: string) {
  const cleaned = value.replace(/^0+(?=\d)/, "");
  return cleaned === "" ? 0 : Number(cleaned);
}

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block">
      <div className="text-xs font-medium text-text-secondary mb-1.5">{label}</div>
      {children}
      {hint && <div className="text-[11px] text-text-light mt-1">{hint}</div>}
    </label>
  );
}

function ErrorText({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] text-destructive mt-1">{children}</div>;
}

function Detail({ label, value, compact = false }: { label: string; value: string; compact?: boolean }) {
  return (
    <div className={compact ? "" : "rounded-xl border border-border bg-background p-4"}>
      <div className="text-[11px] text-text-light font-medium uppercase tracking-wider">{label}</div>
      <div className="mt-1 text-sm text-text-primary capitalize">{value}</div>
    </div>
  );
}

function Stat({ icon: Icon, label, value, tone = "default" }: { icon: any; label: string; value: string; tone?: "default" | "error" }) {
  return (
    <div className={[
      "rounded-xl border bg-surface p-4 shadow-soft",
      tone === "error" ? "border-destructive/30" : "border-border",
    ].join(" ")}>
      <div className={[
        "flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider",
        tone === "error" ? "text-destructive" : "text-text-light",
      ].join(" ")}>
        <Icon className="size-3.5" /> {label}
      </div>
      <div className={"mt-1.5 text-xl font-semibold " + (tone === "error" ? "text-destructive" : "")}>{value}</div>
    </div>
  );
}
