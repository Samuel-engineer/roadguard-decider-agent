import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Card from "./Card";
import { examResponse, situationResponse } from "../test/mockResponses";

describe("Card", () => {
  it("renders an exam card with its title, all options and the selected highlight", () => {
    const card = examResponse.cards[0];
    render(<Card card={card} />);

    expect(screen.getByText(card.title)).toBeInTheDocument();
    for (const option of card.options) {
      expect(screen.getByText(option.label)).toBeInTheDocument();
    }

    const selected = screen.getByText("Ralentir").closest("li");
    expect(selected).toHaveClass("selected");

    const notSelected = screen.getByText("Accélérer").closest("li");
    expect(notSelected).not.toHaveClass("selected");

    expect(
      screen.getByLabelText("Ralentir : 72%"),
    ).toBeInTheDocument();
  });

  it("renders a situation card with Autorisé/Interdit, the selected highlight and a KB excerpt", () => {
    const card = situationResponse.cards[0];
    const excerpt = situationResponse.debug.knowledge_references[0].text;
    render(<Card card={card} kbExcerpt={excerpt} />);

    expect(screen.getByText(card.title)).toBeInTheDocument();
    expect(screen.getByText("Autorisé")).toBeInTheDocument();
    expect(screen.getByText("Interdit")).toBeInTheDocument();

    const allowed = screen.getByText("Autorisé").closest("li");
    expect(allowed).toHaveClass("selected");

    const denied = screen.getByText("Interdit").closest("li");
    expect(denied).not.toHaveClass("selected");

    expect(screen.getByText(excerpt)).toBeInTheDocument();
  });
});
