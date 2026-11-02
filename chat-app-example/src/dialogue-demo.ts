// Fixed replies stand in for the future module. The chat only renders its result.
export type MockProduct = {
  id: string;
  title: string;
  description: string;
  price: number;
  currency: string;
  score: number;
  availability: "in_stock" | "out_of_stock" | "unknown";
  image_url?: string | null;
  attributes: { key: string; label: string; value: string | number; unit?: string }[];
};

export type MockReply = { assistantMessage: string; products: MockProduct[] };
type DialogueStep = { message: string; response: MockReply };

function chandelier(id: string, title: string, description: string, price: number, color: string, shape: string, area: number): MockProduct {
  return {
    id, title, description, price, currency: "RUB", score: 1, availability: "in_stock",
    attributes: [
      { key: "category", label: "Тип товара", value: "chandelier" },
      { key: "color", label: "Цвет", value: color },
      { key: "shape", label: "Форма", value: shape },
      { key: "recommended_area_m2", label: "Заявленная площадь освещения", value: area, unit: "м²" },
    ],
  };
}

const arc = chandelier("chandelier-arc", "Люстра «Дуга»", "Белая · асимметричная · до 16 м²", 18900, "белый", "асимметричная", 16);
const cloud = chandelier("chandelier-cloud", "Люстра «Облако»", "Белая · форма облака · до 10 м²", 15900, "белый", "облако", 10);
const orbit = chandelier("chandelier-orbit", "Люстра «Орбита»", "Белая · круглая · до 15 м²", 12900, "белый", "круглая", 15);
const star = chandelier("chandelier-star", "Люстра «Звезда»", "Золотистая · асимметричная · до 18 м²", 24900, "золотой", "асимметричная", 18);

export const dialogueSteps: DialogueStep[] = [
  {
    message: "Мне нужна люстра в детскую.",
    response: {
      assistantMessage: "Какая площадь комнаты и на какой бюджет ориентируемся? Пока покажу несколько разных вариантов.",
      products: [arc, cloud, star],
    },
  },
  {
    message: "Хочу недорогую, но необычную люстру. Комната — 12 квадратов.",
    response: {
      assistantMessage: "Площадь 12 м² учла. Какую максимальную цену поставить? А под необычной вы имеете в виду цвет или форму? Ниже пока предварительные варианты.",
      products: [arc, cloud, star],
    },
  },
  {
    message: "До 20 тысяч. Белую, необычной формы — например, асимметричную.",
    response: {
      assistantMessage: "Хорошо, белую люстру до 20 000 ₽, желательно асимметричную. «Дуга» ближе всего к этому пожеланию. Она будет основным источником света?",
      products: [arc, cloud, orbit],
    },
  },
  {
    message: "Да, основной свет.",
    response: {
      assistantMessage: "Поняла. Ищем белую люстру для детской 12 м², до 20 000 ₽, желательно асимметричной формы. Оставила два варианта с заявленной площадью от 12 м². «Дуга» — асимметричная, «Орбита» — более доступная альтернатива.",
      products: [arc, orbit],
    },
  },
];

// Replace this response source when the actual module is connected.
export function getDemoReply(step: number): MockReply {
  const entry = dialogueSteps[step];
  if (!entry) throw new RangeError("Неизвестный шаг демонстрационного диалога.");
  return entry.response;
}
