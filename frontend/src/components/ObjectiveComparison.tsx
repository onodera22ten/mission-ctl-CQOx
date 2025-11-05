import React, { useEffect, useState } from "react";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import { compareObjectives } from "../lib/client";

// Sample job IDs for testing
const SAMPLE_JOB_IDS = ["job_1", "job_2"]; // I will need to get real job IDs later

const ObjectiveComparison = () => {
  const [chartData, setChartData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await compareObjectives(SAMPLE_JOB_IDS);
        if (data.ok) {
          setChartData(data.radar_chart_data);
        }
      } catch (error) {
        console.error("Failed to fetch comparison data:", error);
      }
    };

    fetchData();
  }, []);

  if (!chartData) {
    return <div>Loading comparison...</div>;
  }

  return (
    <div style={{ width: "100%", height: 400 }}>
      <h2>Objective Comparison (CAS Scores)</h2>
      <ResponsiveContainer>
        <RadarChart cx="50%" cy="50%" outerRadius="80%" data={chartData.datasets[0].data.map((_, i) => ({ subject: chartData.labels[i], fullMark: 1 }))}>
          <PolarGrid />
          <PolarAngleAxis dataKey="subject" />
          <PolarRadiusAxis angle={30} domain={[0, 1]} />
          <Tooltip />
          <Legend />
          {chartData.datasets.map((dataset, i) => (
            <Radar
              key={dataset.label}
              name={dataset.label}
              dataKey={`value`}
              stroke={`#${Math.floor(Math.random()*16777215).toString(16)}`}
              fill={`#${Math.floor(Math.random()*16777215).toString(16)}`}
              fillOpacity={0.6}
              data={dataset.data.map((value) => ({ value }))}
            />
          ))}
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default ObjectiveComparison;
