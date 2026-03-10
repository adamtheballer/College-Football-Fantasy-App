import { Player } from "@/types/player";
import { injuriesMock } from "@/data/injuriesMock";

const boostProjection = (player: Player, factor: number) => {
  const projection = player.projection;
  if (!projection) return player;
  return {
    ...player,
    projection: {
      ...projection,
      fpts: projection.fpts * factor,
      passingYards: projection.passingYards ? projection.passingYards * factor : projection.passingYards,
      passingTds: projection.passingTds ? projection.passingTds * factor : projection.passingTds,
      rushingYards: projection.rushingYards ? projection.rushingYards * factor : projection.rushingYards,
      rushingTds: projection.rushingTds ? projection.rushingTds * factor : projection.rushingTds,
      receivingYards: projection.receivingYards ? projection.receivingYards * factor : projection.receivingYards,
      receivingTds: projection.receivingTds ? projection.receivingTds * factor : projection.receivingTds,
      receptions: projection.receptions ? projection.receptions * factor : projection.receptions,
    },
  };
};

export const applyInjuryRedistribution = (players: Player[]) => {
  const updated = [...players];
  injuriesMock
    .filter((injury) => injury.status === "OUT")
    .forEach((injury) => {
      const injured = updated.find((p) => p.name.toLowerCase() === injury.name.toLowerCase());
      if (!injured) return;
      const teammates = updated.filter(
        (p) => p.school.toLowerCase() === injured.school?.toLowerCase() && p.id !== injured.id
      );
      if (injured.pos === "WR") {
        const wrs = teammates.filter((p) => p.pos === "WR");
        if (wrs[0]) updated[updated.indexOf(wrs[0])] = boostProjection(wrs[0], 1.12);
        if (wrs[1]) updated[updated.indexOf(wrs[1])] = boostProjection(wrs[1], 1.08);
        const tes = teammates.filter((p) => p.pos === "TE");
        if (tes[0]) updated[updated.indexOf(tes[0])] = boostProjection(tes[0], 1.05);
      }
      if (injured.pos === "RB") {
        const rbs = teammates.filter((p) => p.pos === "RB");
        if (rbs[0]) updated[updated.indexOf(rbs[0])] = boostProjection(rbs[0], 1.2);
        if (rbs[1]) updated[updated.indexOf(rbs[1])] = boostProjection(rbs[1], 1.1);
      }
      if (injured.pos === "TE") {
        const tes = teammates.filter((p) => p.pos === "TE");
        if (tes[0]) updated[updated.indexOf(tes[0])] = boostProjection(tes[0], 1.1);
        const wrs = teammates.filter((p) => p.pos === "WR");
        if (wrs[0]) updated[updated.indexOf(wrs[0])] = boostProjection(wrs[0], 1.05);
      }
    });
  return updated;
};
