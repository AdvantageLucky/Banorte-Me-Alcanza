import { Catalog, BASIC_FUNCTIONS } from '@a2ui/web_core/v0_9';
import {
  Text,
  Image,
  Icon,
  Video,
  AudioPlayer,
  Row,
  Column,
  List,
  Card,
  Tabs,
  Divider,
  Modal,
  Button,
  TextField,
  CheckBox,
  ChoicePicker,
  Slider,
  DateTimeInput,
} from '@a2ui/react/v0_9';
import { StatCard } from './StatCard.jsx';
import { BarChart } from './BarChart.jsx';
import { PlanDePago } from './PlanDePago.jsx';
import { LineChart } from './LineChart.jsx';
import { ApartadoPlanner } from './ApartadoPlanner.jsx';

// Debe ser IDÉNTICO al de src/me_alcanza/backend/a2ui_custom_catalog.py
// (CUSTOM_CATALOG_ID) — no hay generación automática entre ambos lados, se
// mantienen en sync a mano.
export const CUSTOM_CATALOG_ID = 'https://me-alcanza.hackmty.dev/catalogs/v1/catalog.json';

// Catálogo propio del equipo: primitivos base del protocolo A2UI (misma
// implementación de referencia que trae @a2ui/react, reexportados aquí
// individualmente) más los componentes de dominio financiero que diseñamos
// nosotros (StatCard, BarChart, PlanDePago, LineChart, ApartadoPlanner). Un mismo surface puede mezclar
// ambos tipos porque comparten un único catalogId.
export const meAlcanzaCatalog = new Catalog(
  CUSTOM_CATALOG_ID,
  [
    Text,
    Image,
    Icon,
    Video,
    AudioPlayer,
    Row,
    Column,
    List,
    Card,
    Tabs,
    Divider,
    Modal,
    Button,
    TextField,
    CheckBox,
    ChoicePicker,
    Slider,
    DateTimeInput,
    StatCard,
    BarChart,
    PlanDePago,
    LineChart,
    ApartadoPlanner,
  ],
  BASIC_FUNCTIONS,
);
