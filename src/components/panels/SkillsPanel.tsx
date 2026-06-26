"use client";

import { useState, useEffect } from "react";

interface Skill {
  name: string;
  tier: string;
  enabled: boolean;
  methods: string[];
}

export function SkillsPanel() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSkills = async () => {
      try {
        const response = await fetch("/api/skills");
        if (response.ok) {
          const data = await response.json();
          setSkills(data.skills || []);
        }
      } catch (error) {
        console.error("Failed to fetch skills:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchSkills();
  }, []);

  const getTierColor = (tier: string) => {
    const t = tier.toLowerCase();
    if (t === "user_invoked") return "bg-blue-500";
    if (t === "agent_invoked") return "bg-purple-500";
    if (t === "hybrid") return "bg-green-500";
    return "bg-gray-500";
  };

  const handleToggleEnabled = async (skillName: string) => {
    try {
      const response = await fetch(`/api/skills/${skillName}/toggle`, {
        method: "POST",
      });
      if (response.ok) {
        setSkills((prev) =>
          prev.map((s) =>
            s.name === skillName ? { ...s, enabled: !s.enabled } : s
          )
        );
      }
    } catch (error) {
      console.error("Failed to toggle skill:", error);
    }
  };

  const handleRunTestBattery = async () => {
    try {
      const response = await fetch("/api/skills/testing_battery/run", {
        method: "POST",
      });
      if (response.ok) {
        const result = await response.json();
        console.log("Test battery result:", result);
        alert("Test battery completed. Check console for results.");
      }
    } catch (error) {
      console.error("Failed to run test battery:", error);
    }
  };

  if (loading) {
    return (
      <div className="p-6" data-testid="skills-panel">
        <h1 className="text-2xl font-bold mb-6">Skills</h1>
        <p className="text-gray-500">Loading skills...</p>
      </div>
    );
  }

  return (
    <div className="p-6" data-testid="skills-panel">
      <h1 className="text-2xl font-bold mb-6">Skills</h1>

      <div className="space-y-4">
        {skills.length === 0 ? (
          <p className="text-gray-500">No skills registered</p>
        ) : (
          skills.map((skill) => (
            <div
              key={skill.name}
              className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm"
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="font-semibold">{skill.name}</h3>
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs text-white ${getTierColor(
                      skill.tier
                    )}`}
                  >
                    {skill.tier}
                  </span>
                </div>
                <button
                  onClick={() => handleToggleEnabled(skill.name)}
                  className={`px-3 py-1 text-xs rounded ${
                    skill.enabled
                      ? "bg-green-500 text-white hover:bg-green-600"
                      : "bg-gray-300 text-gray-700 hover:bg-gray-400"
                  }`}
                >
                  {skill.enabled ? "Enabled" : "Disabled"}
                </button>
              </div>

              <div>
                <p className="text-xs text-gray-500 mb-1">Methods:</p>
                <div className="flex flex-wrap gap-1">
                  {skill.methods.map((method) => (
                    <span
                      key={method}
                      className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded"
                    >
                      {method}
                    </span>
                  ))}
                </div>
              </div>

              {skill.name === "testing_battery" && (
                <button
                  onClick={handleRunTestBattery}
                  className="mt-3 text-xs text-blue-600 hover:text-blue-800"
                >
                  Run Test Battery
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
