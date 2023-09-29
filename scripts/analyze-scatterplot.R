library(tidyverse)
library(cowplot)

# TODO: setwd("PATH/TO/AAAI-24-Supplementary")

raw <- read_csv("results/export-satcomp.csv", show_col_types = FALSE)

df <- raw %>%
    mutate(time_best = ifelse(time_with_min_up < time_with_min_lim,
                              time_with_min_up, time_with_min_lim))
m <- min(df$time_baseline, df$time_with_min_up, df$time_with_min_lim)


df %>%
    select(instance, time_baseline, time_with_min_up, time_with_min_lim) %>%
    pivot_longer(c(time_with_min_up, time_with_min_lim)) %>%
    mutate(name = ifelse(name == "time_with_min_up", "minimize-UP", ifelse(name == "time_with_min_lim", "minimize-lim", "?"))) %>%
    ggplot() +
    geom_abline(slope = 1, intercept = 0,
                linetype = "dashed", size=0.25) +
    facet_grid(~factor(name, levels=c("minimize-UP", "minimize-lim"))) +
    geom_point(aes(x = value, y = time_baseline,
                   color = value < time_baseline),
               size = 0.5) +
    geom_label(data = tibble(x = c(100, 100),
                             y = c(10000, 10000),
                             label = c(
                                 paste0(df %>% filter(time_with_min_up < time_baseline) %>% nrow(), " / ", df %>% nrow()),
                                 paste0(df %>% filter(time_with_min_lim < time_baseline) %>% nrow(), " / ", df %>% nrow())
                              ),
                             name = c("minimize-UP", "minimize-lim")),
               aes(x = x, y = y, label = label),
               color = "forestgreen", size = 2) +
    scale_color_manual(values = c("FALSE" = "gray20", "TRUE" = "green2")) +
    coord_fixed(xlim = c(m, NA), ylim = c(m, NA)) +
    guides(color = "none") +
    labs(x = "Time (with-derived), s",
         y = "Time (baseline), s") +
    scale_x_log10() +
    scale_y_log10() +
    theme_bw(base_size = 9)
ggsave("plot_scatter_satcomp_both_facet.png", width=3.3, height=1.8, dpi=300)
ggsave("plot_scatter_satcomp_both_facet.pdf", width=3.3, height=1.8)
ggsave("plot_scatter_satcomp_both_facet_large.png", width=5, height=3, dpi=300)
ggsave("plot_scatter_satcomp_both_facet_large.pdf", width=5, height=3)


df %>%
    ggplot() +
    geom_abline(slope = 1, intercept = 0,
                linetype = "dashed") +
    geom_point(aes(x = time_best,
                   y = time_baseline,
                   color = time_best < time_baseline)) +
    scale_color_manual(values = c("FALSE" = "gray20", "TRUE" = "green2")) +
    coord_fixed(xlim = c(m, NA), ylim = c(m, NA)) +
    scale_x_log10() +
    scale_y_log10() +
    labs(
        x = "Time (with-derived, best), s",
        y = "Time (original), s",
    ) +
    guides(color = "none") +
    theme_bw(base_size = 9)
ggsave("plot_scatter_satcomp_best.pdf", width=4, height=2, dpi=300)
ggsave("plot_scatter_satcomp_best.png", width=4, height=2)
